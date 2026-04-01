"""
火山引擎同声传译API客户端封装
基于已有的ast_python_client进行优化和简化
"""

import asyncio
import uuid
import logging
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
import websockets
from websockets import Headers



# NOTE: 不再手动操纵 sys.path。
# 生产环境由 Tauri 通过 _pth / PYTHONPATH 设置搜索路径；
# 开发环境依赖 CWD 或 IDE 配置的 PYTHONPATH。

logger = logging.getLogger(__name__)


def _ensure_protobuf_runtime_compat():
    """兼容旧版 protobuf 运行时，避免缺少 runtime_version 模块导致导入失败。"""
    try:
        from google.protobuf import runtime_version as _runtime_version  # noqa: F401
        return
    except ImportError:
        compat_module = types.ModuleType("google.protobuf.runtime_version")

        class Domain:
            PUBLIC = "PUBLIC"
            INTERNAL = "INTERNAL"

        def validate_protobuf_runtime_version(*args, **kwargs):
            return None

        compat_module.Domain = Domain
        compat_module.ValidateProtobufRuntimeVersion = validate_protobuf_runtime_version
        sys.modules["google.protobuf.runtime_version"] = compat_module


def _ensure_repo_package_alias():
    """开发态从仓库根目录启动时，为 generated pb2 提供包名别名。"""
    if "realtime_translator" in sys.modules:
        return

    package_module = types.ModuleType("realtime_translator")
    package_module.__path__ = [str(Path(__file__).resolve().parents[1])]
    sys.modules["realtime_translator"] = package_module


_ensure_protobuf_runtime_compat()
_ensure_repo_package_alias()

# 错误分类: 可重试的临时性错误
RETRYABLE_ERRORS = {
    "Engine:1022",  # 模型推理错误
    "ServerInternalError",  # 服务器内部错误
    "Model inference error",  # 模型推理错误
    "timeout",  # 超时
    "network",  # 网络错误
    "connection",  # 连接错误
}

# 错误分类: 不可重试的永久性错误
FATAL_ERRORS = {
    "authentication",  # 认证失败
    "quota",  # 配额超限
    "invalid_parameter",  # 参数错误
    "invalid_app_key",  # 应用密钥无效
    "invalid_access_key",  # 访问密钥无效
}

# 导入火山引擎 protobuf 定义。
# 优先走打包后的包路径；开发态从仓库根目录直接运行时退回本地 pb2 目录。
try:
    from realtime_translator.pb2.products.understanding.ast.ast_service_pb2 import (
        TranslateRequest, TranslateResponse
    )
    from realtime_translator.pb2.common.events_pb2 import Type
except ModuleNotFoundError:
    from pb2.products.understanding.ast.ast_service_pb2 import (
        TranslateRequest, TranslateResponse
    )
    from pb2.common.events_pb2 import Type

# 字幕相关事件名称映射，便于日志中直接识别生命周期阶段
EVENT_NAME_MAP = {
    Type.SessionStarted: "SessionStarted",
    Type.SourceSubtitleStart: "SourceSubtitleStart",
    Type.SourceSubtitleResponse: "SourceSubtitleResponse",
    Type.SourceSubtitleEnd: "SourceSubtitleEnd",
    Type.TranslationSubtitleStart: "TranslationSubtitleStart",
    Type.TranslationSubtitleResponse: "TranslationSubtitleResponse",
    Type.TranslationSubtitleEnd: "TranslationSubtitleEnd",
    Type.SessionFinished: "SessionFinished",
    Type.SessionFailed: "SessionFailed",
    Type.SessionCanceled: "SessionCanceled",
    Type.UsageResponse: "UsageResponse",
}

logger.info("✅ 成功导入火山引擎protobuf定义（内部版本）")


@dataclass
class VolcengineConfig:
    """火山引擎API配置"""
    ws_url: str
    app_key: str
    access_key: str
    resource_id: str = "volc.service_type.10053"


@dataclass
class TranslationResult:
    """翻译结果"""
    event: int
    session_id: str
    sequence: int
    text: str = ""
    audio_data: bytes = b""
    is_finished: bool = False
    is_failed: bool = False
    error_message: str = ""


class VolcengineTranslator:
    """火山引擎翻译客户端"""

    def __init__(
        self,
        config: VolcengineConfig,
        mode: str = "s2s",
        source_language: str = "zh",
        target_language: str = "en",
        result_callback: Optional[Callable] = None,
        auto_reconnect: bool = True,
        max_retry_attempts: int = 3,
        retry_delay_base: float = 1.0,
        failure_callback: Optional[Callable] = None
    ):
        """
        初始化翻译客户端

        Args:
            config: 火山引擎配置
            mode: 翻译模式 ("s2s"=语音转语音, "s2t"=语音转文本)
            source_language: 源语言 ("zh"=中文, "en"=英文)
            target_language: 目标语言
            result_callback: 结果回调函数
            auto_reconnect: 是否自动重连 (默认True)
            max_retry_attempts: 最大重试次数 (默认3)
            retry_delay_base: 重试基础延迟(秒) (默认1.0, 使用指数退避)
            failure_callback: 失败回调函数(重试失败后调用)
        """
        self.config = config
        self.mode = mode
        self.source_language = source_language
        self.target_language = target_language
        self.result_callback = result_callback
        self.failure_callback = failure_callback

        # 自动重连配置
        self.auto_reconnect = auto_reconnect
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_base = retry_delay_base

        self.conn = None
        self.session_id = None
        self.is_connected = False
        self.is_session_active = False

        # 音频格式配置
        self.source_audio_format = "wav"
        self.source_audio_rate = 16000
        self.source_audio_bits = 16
        self.source_audio_channel = 1

        self.target_audio_format = "ogg_opus"
        self.target_audio_rate = 24000

    async def connect(self):
        """建立WebSocket连接"""
        if self.is_connected:
            logger.warning("⚠️  已存在WebSocket连接")
            return

        try:
            conn_id = str(uuid.uuid4())
            headers = Headers({
                "X-Api-App-Key": self.config.app_key,
                "X-Api-Access-Key": self.config.access_key,
                "X-Api-Resource-Id": self.config.resource_id,
                "X-Api-Connect-Id": conn_id
            })

            self.conn = await websockets.connect(
                self.config.ws_url,
                additional_headers=headers,  # websockets 14+ (旧版用 extra_headers)
                max_size=1000000000,
                ping_interval=None
            )

            self.is_connected = True
            # websockets 14+ 使用 conn.response.headers;13.x 使用 conn.response_headers
            try:
                resp_headers = self.conn.response.headers  # websockets 14+
            except AttributeError:
                resp_headers = getattr(self.conn, 'response_headers', {})
            log_id = resp_headers.get('X-Tt-Logid', 'unknown') if resp_headers else 'unknown'
            logger.info(f"✅ WebSocket已连接 (LogID: {log_id})")

        except Exception as e:
            logger.error(f"❌ WebSocket连接失败: {e}")
            # 尝试从异常中提取LogID (如果连接失败)
            try:
                resp_headers = None
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    resp_headers = e.response.headers  # websockets 14+
                elif hasattr(e, 'response_headers'):
                    resp_headers = e.response_headers  # websockets 13.x
                if resp_headers:
                    log_id = resp_headers.get('X-Tt-Logid', 'unknown')
                    logger.error(f"   LogID: {log_id}")
            except:
                pass
            raise

    async def start_session(self):
        """启动翻译会话"""
        if not self.is_connected:
            raise RuntimeError("WebSocket未连接")

        if self.is_session_active:
            logger.warning("⚠️  会话已启动")
            return

        try:
            self.session_id = str(uuid.uuid4())

            # 构建StartSession请求
            request = TranslateRequest()
            request.request_meta.SessionID = self.session_id
            request.event = Type.StartSession
            request.user.uid = "realtime_translator"
            request.user.did = "realtime_translator"

            # 源音频配置
            request.source_audio.format = self.source_audio_format
            request.source_audio.rate = self.source_audio_rate
            request.source_audio.bits = self.source_audio_bits
            request.source_audio.channel = self.source_audio_channel

            # 目标音频配置(仅s2s模式需要)
            if self.mode == "s2s":
                request.target_audio.format = self.target_audio_format
                request.target_audio.rate = self.target_audio_rate

            # 翻译参数
            request.request.mode = self.mode
            request.request.source_language = self.source_language
            request.request.target_language = self.target_language

            # 🔍 调试日志: 会话配置
            logger.info(f"🔧 [Session启动配置]")
            logger.info(f"   模式: {self.mode}")
            logger.info(f"   源语言: {self.source_language} → 目标语言: {self.target_language}")
            logger.info(f"   源音频: {self.source_audio_format}, {self.source_audio_rate}Hz, {self.source_audio_bits}bit, {self.source_audio_channel}ch")
            if self.mode == "s2s":
                logger.info(f"   目标音频格式: {self.target_audio_format}, {self.target_audio_rate}Hz")
                logger.info(f"   ⚠️  request.target_audio.format = {request.target_audio.format}")
                logger.info(f"   ⚠️  request.target_audio.rate = {request.target_audio.rate}")
                # 检查target_audio是否为空
                if not request.target_audio.format:
                    logger.error(f"   ❌ target_audio.format 为空!")
                if not request.target_audio.rate:
                    logger.error(f"   ❌ target_audio.rate 为0!")
            else:
                logger.info(f"   目标音频: 无(s2t模式)")

            # 🔍 调试: 检查request内容
            logger.debug(f"   request.request.mode = {request.request.mode}")
            logger.debug(f"   request序列化大小: {len(request.SerializeToString())} bytes")

            # 发送请求
            await self.conn.send(request.SerializeToString())

            # 接收响应
            response_data = await self.conn.recv()
            response = TranslateResponse()
            response.ParseFromString(response_data)

            if response.event != Type.SessionStarted:
                error_msg = f"会话启动失败: {response.response_meta.Message}"
                logger.error(f"❌ {error_msg}")
                raise RuntimeError(error_msg)

            self.is_session_active = True
            logger.info(f"✅ 翻译会话已启动 (ID: {self.session_id})")
            logger.info(f"   模式: {self.mode}, {self.source_language}→{self.target_language}")

        except Exception as e:
            logger.error(f"❌ 启动会话失败: {e}")
            raise

    async def send_audio(self, audio_data: bytes):
        """
        发送音频数据

        Args:
            audio_data: 音频字节流
        """
        if not self.is_session_active:
            raise RuntimeError("会话未启动")

        try:
            request = TranslateRequest()
            request.request_meta.SessionID = self.session_id
            request.event = Type.TaskRequest
            request.source_audio.binary_data = audio_data

            await self.conn.send(request.SerializeToString())

        except Exception as e:
            logger.error(f"❌ 发送音频失败: {e}")
            raise

    async def receive_result(self) -> Optional[TranslationResult]:
        """
        接收翻译结果

        Returns:
            翻译结果,如果会话结束返回None
        """
        if not self.is_session_active:
            return None

        try:
            response_data = await self.conn.recv()
            response = TranslateResponse()
            response.ParseFromString(response_data)

            # 调试日志: 记录所有响应事件
            event_name = EVENT_NAME_MAP.get(response.event, f"Unknown({response.event})")

            # 🔍 详细响应日志
            audio_size = len(response.data) if response.data else 0
            text_preview = response.text[:20] + "..." if len(response.text) > 20 else response.text if response.text else ""

            logger.debug(
                f"📨 收到响应: event={event_name}, "
                f"text={'有' if response.text else '无'}, "
                f"audio={'有' if response.data else '无'}, "
                f"seq={response.response_meta.Sequence}"
            )

            # 🔍 音频数据详情
            if audio_size > 0:
                logger.debug(f"   🎵 音频数据: {audio_size} bytes")
            else:
                logger.debug(f"   ❌ 音频数据为空!")

            # 🔍 文本详情
            if response.text:
                logger.debug(f"   📝 文本内容: '{text_preview}'")

            # 🔍 原始响应大小
            logger.debug(f"   📦 原始响应大小: {len(response_data)} bytes")

            result = TranslationResult(
                event=response.event,
                session_id=response.response_meta.SessionID,
                sequence=response.response_meta.Sequence,
                text=response.text if response.text else "",
                audio_data=response.data if response.data else b"",
                is_finished=(response.event == Type.SessionFinished),
                is_failed=(response.event in [Type.SessionFailed, Type.SessionCanceled]),
                error_message=response.response_meta.Message if response.response_meta.Message else ""
            )

            # 检查会话状态
            if result.is_finished:
                logger.info(f"✅ 会话正常结束")
                self.is_session_active = False
            elif result.is_failed:
                logger.error(f"❌ 会话失败: {result.error_message}")
                self.is_session_active = False

                # 🆕 自动重连逻辑
                if self.auto_reconnect:
                    logger.warning("🔄 启动自动恢复...")
                    recovery_success = await self._attempt_recovery(result.error_message)

                    if recovery_success:
                        logger.info("✅ 自动恢复成功,会话已重启")
                        # 更新result标记,表明已恢复
                        result.is_failed = False
                        result.error_message = "已自动恢复"
                    else:
                        logger.error("❌ 自动恢复失败,会话终止")
                else:
                    logger.warning("⚠️  自动重连已禁用,会话终止")

            # 调用回调
            if self.result_callback and response.event != Type.UsageResponse:
                self.result_callback(result)

            return result

        except Exception as e:
            logger.error(f"❌ 接收结果失败: {e}")
            return None

    def _should_retry(self, error_msg: str) -> bool:
        """
        判断错误是否应该重试

        Args:
            error_msg: 错误消息

        Returns:
            是否应该重试
        """
        if not error_msg:
            return False

        error_lower = error_msg.lower()

        # 检查是否为致命错误(不可重试)
        if any(fatal in error_lower for fatal in FATAL_ERRORS):
            logger.warning(f"⚠️  检测到致命错误,不可重试: {error_msg}")
            return False

        # 检查是否为可重试错误
        if any(retry in error_msg for retry in RETRYABLE_ERRORS):
            logger.info(f"✅ 检测到可重试错误: {error_msg}")
            return True

        # 默认: 未知错误,谨慎处理,不重试
        logger.warning(f"⚠️  未知错误类型,默认不重试: {error_msg}")
        return False

    async def _attempt_recovery(self, error: str) -> bool:
        """
        尝试恢复会话(自动重连)

        Args:
            error: 错误消息

        Returns:
            是否恢复成功
        """
        # 检查是否应该重试
        if not self._should_retry(error):
            logger.error(f"❌ 错误不可重试,放弃恢复")
            return False

        logger.info(f"🔄 开始自动恢复流程...")

        for attempt in range(1, self.max_retry_attempts + 1):
            try:
                # 指数退避延迟
                delay = self.retry_delay_base * (2 ** (attempt - 1))
                logger.warning(
                    f"🔄 尝试重启会话 ({attempt}/{self.max_retry_attempts})..."
                )
                logger.info(f"⏳ 等待 {delay:.1f}秒...")

                await asyncio.sleep(delay)

                # 检查WebSocket是否还连接
                if not self.is_connected or not self.conn:
                    logger.info("🔌 重新建立WebSocket连接...")
                    await self.connect()

                # 重启会话
                logger.info("📡 重新启动翻译会话...")
                await self.start_session()

                logger.info(f"✅ 会话恢复成功!")
                return True

            except Exception as e:
                logger.error(
                    f"❌ 恢复失败 ({attempt}/{self.max_retry_attempts}): {e}"
                )

                if attempt == self.max_retry_attempts:
                    logger.error("❌ 已达最大重试次数,会话无法恢复")

                    # 调用失败回调(如果有)
                    if self.failure_callback:
                        try:
                            self.failure_callback(error)
                        except Exception as callback_error:
                            logger.error(f"❌ 失败回调执行出错: {callback_error}")

                    return False

        return False

    async def finish_session(self):
        """结束翻译会话"""
        if not self.is_session_active:
            return

        try:
            request = TranslateRequest()
            request.request_meta.SessionID = self.session_id
            request.event = Type.FinishSession

            await self.conn.send(request.SerializeToString())
            logger.info("📤 已发送FinishSession请求")

            # 等待会话结束响应
            while self.is_session_active:
                result = await self.receive_result()
                if result and (result.is_finished or result.is_failed):
                    break

        except Exception as e:
            logger.error(f"❌ 结束会话失败: {e}")

    async def close(self):
        """关闭连接"""
        if self.is_session_active:
            await self.finish_session()

        if self.is_connected and self.conn:
            await self.conn.close()
            self.is_connected = False
            logger.info("🔌 WebSocket连接已关闭")


async def test_translator():
    """测试翻译客户端"""
    logging.basicConfig(level=logging.INFO)

    # 配置(需要替换为真实的密钥)
    config = VolcengineConfig(
        ws_url="wss://openspeech.bytedance.com/api/v4/ast/v2/translate",
        app_key="your_app_key",
        access_key="your_access_key"
    )

    # 创建翻译器
    translator = VolcengineTranslator(
        config=config,
        mode="s2t",  # 测试语音转文本
        source_language="zh",
        target_language="en"
    )

    try:
        # 连接
        await translator.connect()

        # 启动会话
        await translator.start_session()

        # 这里应该发送真实的音频数据
        # await translator.send_audio(audio_data)

        # 接收结果
        # result = await translator.receive_result()

    except Exception as e:
        print(f"测试失败: {e}")

    finally:
        await translator.close()


if __name__ == "__main__":
    asyncio.run(test_translator())
