"""
Protobuf 导入测试脚本
验证迁移后的 pb2 模块是否可正常导入和使用
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_imports():
    """测试所有必要的导入"""
    print("🧪 开始 Protobuf 导入测试...\n")

    try:
        print("1️⃣  导入 events_pb2...")
        from realtime_translator.pb2.common import events_pb2
        print("   ✅ 成功导入 events_pb2")
        print(f"   - Type.StartSession 值: {events_pb2.Type.StartSession}")

        print("\n2️⃣  导入 rpcmeta_pb2...")
        from realtime_translator.pb2.common import rpcmeta_pb2
        print("   ✅ 成功导入 rpcmeta_pb2")

        print("\n3️⃣  导入 au_base_pb2...")
        from realtime_translator.pb2.products.understanding.base import au_base_pb2
        print("   ✅ 成功导入 au_base_pb2")

        print("\n4️⃣  导入 ast_service_pb2...")
        from realtime_translator.pb2.products.understanding.ast import ast_service_pb2
        print("   ✅ 成功导入 ast_service_pb2")

        print("\n5️⃣  导入 TranslateRequest 和 TranslateResponse...")
        from realtime_translator.pb2.products.understanding.ast.ast_service_pb2 import (
            TranslateRequest, TranslateResponse
        )
        print("   ✅ 成功导入 TranslateRequest 和 TranslateResponse")

        print("\n6️⃣  导入 Type 枚举...")
        from realtime_translator.pb2.common.events_pb2 import Type
        print("   ✅ 成功导入 Type 枚举")
        print(f"   - Type.StartSession: {Type.StartSession}")
        print(f"   - Type.SessionStarted: {Type.SessionStarted}")
        print(f"   - Type.TranslationSubtitleResponse: {Type.TranslationSubtitleResponse}")

        print("\n7️⃣  创建 Protobuf 对象...")
        req = TranslateRequest()
        resp = TranslateResponse()
        print("   ✅ 成功创建 TranslateRequest 和 TranslateResponse 对象")
        print(f"   - TranslateRequest 对象: {type(req)}")
        print(f"   - TranslateResponse 对象: {type(resp)}")

        print("\n" + "="*60)
        print("✅ 所有导入测试通过！")
        print("="*60)
        return True

    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        print(f"\n   检查清单:")
        print(f"   - 确保 pb2 目录结构存在")
        print(f"   - 确保所有 __init__.py 文件都已创建")
        print(f"   - 确保 pb2 文件内部导入已更新")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_volcengine_client():
    """测试 volcengine_client 是否可正常导入"""
    print("\n" + "="*60)
    print("🧪 测试 volcengine_client 导入...\n")

    try:
        from realtime_translator.core.volcengine_client import (
            VolcengineTranslator, VolcengineConfig, TranslationResult
        )
        print("✅ 成功导入 VolcengineTranslator")
        print("✅ 成功导入 VolcengineConfig")
        print("✅ 成功导入 TranslationResult")

        # 测试创建对象
        print("\n📝 测试对象创建...")
        config = VolcengineConfig(
            ws_url="wss://test.example.com",
            app_key="test_key",
            access_key="test_access"
        )
        print(f"✅ 成功创建 VolcengineConfig: {config}")

        translator = VolcengineTranslator(config)
        print(f"✅ 成功创建 VolcengineTranslator")

        print("\n" + "="*60)
        print("✅ VolcengineClient 导入测试通过！")
        print("="*60)
        return True

    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success_imports = test_imports()
    success_client = test_volcengine_client()

    sys.exit(0 if (success_imports and success_client) else 1)
