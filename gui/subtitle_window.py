"""
悬浮字幕窗口模块
显示对方英文翻译成的中文字幕
"""

import tkinter as tk
from tkinter import font, scrolledtext
import threading
import logging
import re
import textwrap
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class SubtitleWindow:
    """
    悬浮字幕窗口
    显示对方英文翻译成的中文字幕

    特性:
    - 半透明背景
    - 置顶显示
    - 可拖动
    - 双击切换字体大小
    - ESC键隐藏/显示
    """

    def __init__(self,
                 width: int = 800,
                 height: int = 100,
                 font_size: int = 24,
                 bg_color: str = "#000000",
                 text_color: str = "#FFFFFF",
                 opacity: float = 0.8,
                 position: str = "top_center",
                 max_history: int = 10,
                 show_timestamp: bool = False):
        """
        初始化字幕窗口

        Args:
            width: 窗口宽度
            height: 窗口高度
            font_size: 字体大小
            bg_color: 背景色(十六进制)
            text_color: 文字色(十六进制)
            opacity: 不透明度 (0.0-1.0)
            position: 位置 ("top_center", "bottom_center", "top_left", etc.)
            max_history: 最大历史记录条数
            show_timestamp: 是否显示时间戳
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.bg_color = bg_color
        self.text_color = text_color
        self.opacity = opacity
        self.position = position
        self.max_history = max_history
        self.show_timestamp = show_timestamp

        self.window = None
        self.label = None
        self.text_widget = None  # 多行文本控件
        self.is_visible = True
        self.is_large_font = False
        self.current_font_size = font_size

        # 🆕 双缓冲区架构
        # 缓冲区1: 原始流式数据（完整记录火山引擎的所有输出）
        self.raw_buffer = deque(maxlen=max_history * 10)  # 保留更多原始数据用于调试

        # 缓冲区2: 最终展示数据（智能去重后的结果）
        self.display_buffer = deque(maxlen=max_history)

        # 向后兼容：保留 subtitle_history 作为 display_buffer 的别名
        self.subtitle_history = self.display_buffer

        # 展示层配置（避免排版拥挤）
        # 仅显示最近若干条，历史仍完整保留在 buffer 中
        self.display_limit = min(5, max(2, self.max_history))

        # 拖动相关
        self.drag_x = 0
        self.drag_y = 0

        logger.info("🎬 悬浮字幕窗口初始化")
        logger.info(f"   尺寸: {width}x{height}")
        logger.info(f"   字体: {font_size}pt")
        logger.info(f"   不透明度: {opacity * 100:.0f}%")
        logger.info(f"   位置: {position}")
        logger.info(f"   历史记录: {max_history}条")

    def create(self):
        """创建Tkinter窗口"""
        logger.info("🚀 创建字幕窗口...")

        self.window = tk.Tk()
        self.window.title("字幕窗口")

        # 窗口设置
        self.window.geometry(f"{self.width}x{self.height}")
        self.window.configure(bg=self.bg_color)
        self.window.overrideredirect(True)  # 无边框
        self.window.attributes('-topmost', True)  # 置顶
        self.window.attributes('-alpha', self.opacity)  # 透明度

        # 计算位置
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        if self.position == "top_center":
            x = (screen_width - self.width) // 2
            y = 50
        elif self.position == "bottom_center":
            x = (screen_width - self.width) // 2
            y = screen_height - self.height - 100
        elif self.position == "top_left":
            x = 50
            y = 50
        elif self.position == "top_right":
            x = screen_width - self.width - 50
            y = 50
        else:
            # 默认居中
            x = (screen_width - self.width) // 2
            y = 50

        self.window.geometry(f"+{x}+{y}")

        # 创建字幕文本控件(支持多行显示和滚动)
        subtitle_font = font.Font(
            family="Microsoft YaHei",
            size=self.font_size,
            weight="normal"  # 多行文本用normal更清晰
        )

        # 使用Text控件代替Label,支持多行和滚动
        self.text_widget = tk.Text(
            self.window,
            font=subtitle_font,
            bg=self.bg_color,
            fg=self.text_color,
            wrap=tk.WORD,  # 自动换行
            relief=tk.FLAT,  # 无边框
            highlightthickness=0,  # 无高亮边框
            state=tk.DISABLED,  # 禁止用户编辑
            cursor="arrow",  # 鼠标样式
            spacing1=4,
            spacing2=3,
            spacing3=10,
            padx=10,
            pady=10
        )
        self.text_widget.pack(expand=True, fill='both', padx=10, pady=10)

        # 初始提示
        self._update_text_widget("等待字幕...")

        # 绑定事件
        self.window.bind('<Button-1>', self._start_drag)
        self.window.bind('<B1-Motion>', self._on_drag)
        self.window.bind('<Double-Button-1>', self._toggle_font_size)
        self.window.bind('<Escape>', self._toggle_visibility)

        # 绑定关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)

        logger.info(f"✅ 字幕窗口已创建: {self.width}x{self.height} @ ({x}, {y})")
        logger.info("   操作提示:")
        logger.info("   - 左键拖动: 移动窗口")
        logger.info("   - 双击: 切换字体大小")
        logger.info("   - ESC: 隐藏/显示窗口")

    def _start_drag(self, event):
        """开始拖动"""
        self.drag_x = event.x
        self.drag_y = event.y

    def _on_drag(self, event):
        """拖动过程"""
        x = self.window.winfo_x() + event.x - self.drag_x
        y = self.window.winfo_y() + event.y - self.drag_y
        self.window.geometry(f"+{x}+{y}")

    def _toggle_font_size(self, event):
        """切换字体大小"""
        self.is_large_font = not self.is_large_font
        new_size = int(self.font_size * 1.3) if self.is_large_font else self.font_size

        subtitle_font = font.Font(
            family="Microsoft YaHei",
            size=new_size,
            weight="normal"
        )

        if self.text_widget:
            self.text_widget.configure(font=subtitle_font)

        self.current_font_size = new_size
        logger.info(f"🔤 字体大小切换: {new_size}pt")

    def _toggle_visibility(self, event):
        """切换可见性"""
        self.is_visible = not self.is_visible

        if self.is_visible:
            self.window.deiconify()
        else:
            self.window.withdraw()

        logger.info(f"👁️  字幕窗口: {'显示' if self.is_visible else '隐藏'}")

    def _on_closing(self):
        """窗口关闭事件"""
        logger.info("🛑 字幕窗口关闭")
        self.window.destroy()

    def _update_text_widget(self, content: str):
        """内部方法:更新Text控件内容"""
        if self.text_widget:
            self.text_widget.configure(state=tk.NORMAL)  # 允许编辑
            self.text_widget.delete(1.0, tk.END)  # 清空
            self.text_widget.insert(1.0, content)  # 插入新内容
            self.text_widget.configure(state=tk.DISABLED)  # 禁止编辑
            # 自动滚动到底部
            self.text_widget.see(tk.END)

    def _extract_text_content(self, entry: str) -> str:
        """
        提取字幕条目的纯文本内容(去除时间戳)

        Args:
            entry: 字幕条目(可能包含时间戳)

        Returns:
            纯文本内容
        """
        if self.show_timestamp and entry.startswith('['):
            # 格式: [HH:MM:SS] text
            # 找到第一个 ] 后的内容
            idx = entry.find(']')
            if idx != -1:
                return entry[idx + 1:].strip()
        return entry.strip()

    def _is_text_similar(self, text1: str, text2: str, threshold: float = 0.7) -> bool:
        """
        判断两个文本是否相似(包含关系或高重叠度)

        Args:
            text1: 文本1
            text2: 文本2
            threshold: 相似度阈值 (0.0-1.0)

        Returns:
            是否相似
        """
        if not text1 or not text2:
            return False

        # 完全相同
        if text1 == text2:
            return True

        # 包含关系(一个是另一个的子串)
        if text1 in text2 or text2 in text1:
            return True

        # 前缀匹配(新文本是旧文本的扩展)
        if text2.startswith(text1) or text1.startswith(text2):
            return True

        # 字符重叠度计算(防止完全不同的文本被误判)
        text1_chars = set(text1)
        text2_chars = set(text2)
        common_chars = text1_chars & text2_chars

        if not common_chars:
            return False

        # 计算重叠率(使用Jaccard相似度)
        overlap_ratio = len(common_chars) / len(text1_chars | text2_chars)
        return overlap_ratio >= threshold

    def _is_english_text(self, text: str) -> bool:
        """
        判断文本是否主要为英文

        Args:
            text: 待检测文本

        Returns:
            是否为英文文本
        """
        if not text:
            return False

        # 统计拉丁字母和中文字符
        latin_chars = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')

        total_chars = latin_chars + chinese_chars

        if total_chars == 0:
            return False

        # 如果拉丁字母占比超过50%,认为是英文
        return (latin_chars / total_chars) > 0.5

    def _normalize_text(self, text: str) -> str:
        """规范化文本，减少排版混乱"""
        if not text:
            return ""

        # 统一换行与空白
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n{2,}", "\n", t)
        t = t.strip()
        return t

    def _beautify_chinese(self, text: str) -> str:
        """中文排版清洗：去异常空格、收敛标点、提升可读性"""
        if not text:
            return ""

        t = text.strip()
        # 去掉中文之间被误插入的空格：如“我 们”->“我们”
        t = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", t)
        # 中文标点前后空格清理
        t = re.sub(r"\s*([，。！？；：、])\s*", r"\1", t)
        # 多个连续中文标点压缩
        t = re.sub(r"([，。！？；：、])\1+", r"\1", t)
        # 中英文夹杂时，英文与中文之间保留单空格更清晰
        t = re.sub(r"(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])", " ", t)
        t = re.sub(r"(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])", " ", t)
        # 全局多空格收敛
        t = re.sub(r"\s{2,}", " ", t)

        # 句读优先换行：长句在逗号/句号后断行，阅读更稳
        t = re.sub(r"([，。！？；])", r"\1\n", t)
        t = re.sub(r"\n{2,}", "\n", t)
        return t.strip()

    def _smart_wrap(self, text: str, width: int = 32) -> str:
        """中英文友好的轻量换行"""
        if not text:
            return ""

        # 若已存在换行，逐行处理
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        wrapped = []
        for ln in lines:
            if self._is_english_text(ln):
                wrapped.extend(textwrap.wrap(ln, width=width, break_long_words=False, break_on_hyphens=False) or [ln])
            else:
                ln = self._beautify_chinese(ln)
                wrapped.extend(textwrap.wrap(ln, width=width, break_long_words=True, break_on_hyphens=False) or [ln])
        return "\n".join(wrapped)

    def _format_display_text(self) -> str:
        """构建最终展示文本（只显示最近N条，排版更紧凑）"""
        if not self.subtitle_history:
            return "等待字幕..."

        recent_entries = list(self.subtitle_history)[-self.display_limit:]
        cleaned = []

        for entry in recent_entries:
            t = self._normalize_text(entry)
            if not t:
                continue

            # 针对 EN/ZH 双行格式做更清晰排版
            lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
            en_line = next((ln for ln in lines if ln.startswith("EN")), "")
            zh_line = next((ln for ln in lines if ln.startswith("ZH")), "")

            if en_line or zh_line:
                block = []
                # 中文优先显示在上方，阅读更自然
                if zh_line:
                    zh_text = zh_line[2:].strip(":： ")
                    zh_text = self._beautify_chinese(zh_text)
                    block.append("【中文】\n" + self._smart_wrap(zh_text, width=26))
                if en_line:
                    en_text = en_line[2:].strip(":： ")
                    block.append("【English】\n" + self._smart_wrap(en_text, width=38))
                cleaned.append("\n".join(block))
            else:
                # 没有标签时按中文优先策略排版
                nt = self._beautify_chinese(t)
                cleaned.append(self._smart_wrap(nt, width=26 if not self._is_english_text(nt) else 38))

        if not cleaned:
            return "等待字幕..."

        # 使用更轻分隔，避免视觉拥挤
        return "\n··········\n".join(cleaned)

    def _check_merge_candidates(self, current_text: str, lookback_count: int = 10) -> int:
        """
        检查新文本是否为最近N条的合并结果
        🔧 修复: 只合并连续的片段，遇到完整句子就停止（避免删除历史完整内容）

        Args:
            current_text: 当前新文本
            lookback_count: 向前检查的条数

        Returns:
            应该删除的旧条目数量(0表示不需要合并)
        """
        if not self.subtitle_history or len(current_text) < 3:
            return 0

        # 向前检查最近N条
        check_count = min(lookback_count, len(self.subtitle_history))
        # 🔧 修复: 将deque转为list再切片,避免切片索引错误
        recent_entries = list(self.subtitle_history)[-check_count:]

        # 提取纯文本
        recent_texts = [self._extract_text_content(entry) for entry in recent_entries]

        # 🔧 新增: 从最近的条目往前找，只考虑连续的片段（遇到完整句子就停止）
        max_fragment_count = 0
        for i in range(len(recent_texts) - 1, -1, -1):
            text = recent_texts[i]
            # 检查是否为完整句子（≥8字符，去除标点和空格）
            clean_text = text.replace(" ", "").replace("，", "").replace("。", "").replace("、", "")
            if len(clean_text) >= 8:
                # 遇到完整句子，停止（只考虑之后的片段）
                max_fragment_count = len(recent_texts) - 1 - i
                break
        else:
            # 全部都是片段
            max_fragment_count = len(recent_texts)

        # 如果没有找到任何片段，直接返回
        if max_fragment_count == 0:
            return 0

        # 尝试不同长度的合并窗口(从长到短)，但不超过max_fragment_count
        for merge_count in range(min(max_fragment_count, check_count), 1, -1):
            # 取最近的merge_count条
            texts_to_merge = recent_texts[-merge_count:]

            # 合并这些文本(去除空格)
            merged = "".join(texts_to_merge).replace(" ", "")
            current_clean = current_text.replace(" ", "")

            # 检查合并后的文本是否在新文本中
            if merged in current_clean or current_clean in merged:
                # 检查重叠度(避免误判)
                overlap = len(merged) / max(len(merged), len(current_clean))
                if overlap > 0.6:  # 至少60%重叠
                    logger.debug(
                        f"🔗 检测到合并: {merge_count}条片段 → '{current_text[:30]}...' "
                        f"(重叠度: {overlap:.1%})"
                    )
                    return merge_count

        return 0

    def update_subtitle(self, text: str):
        """
        更新字幕文本(线程安全) - 双缓冲区架构

        数据流:
        1. 所有输入先记录到 raw_buffer (原始数据，完整记录)
        2. 智能去重逻辑处理后写入 display_buffer (展示数据)
        3. 字幕窗口从 display_buffer 读取显示

        智能去重功能:
        - 完全相同的文本会被跳过
        - 如果新文本是最近多条的合并,会删除旧条目并添加新的
        - 包含关系或扩展文本会覆盖前一条
        - 完全不同的文本会作为新条目添加

        Args:
            text: 字幕文本
        """
        if not text or not text.strip():
            return

        # 提取纯文本内容用于比较（先规范化，减少乱排版）
        current_text = self._normalize_text(text)

        # 构建新条目
        if self.show_timestamp:
            timestamp = datetime.now().strftime("%H:%M:%S")
            new_entry = f"[{timestamp}] {text}"
        else:
            new_entry = text

        # 🆕 步骤1: 先记录到原始缓冲区（保留所有火山引擎输出）
        self.raw_buffer.append({
            'timestamp': datetime.now(),
            'text': current_text,
            'entry': new_entry
        })

        # 智能去重和合并逻辑
        if self.subtitle_history:
            # 步骤0: 检查是否为英文翻译(火山引擎模式: 中文片段 → 完整中文 → 英文)
            if self._is_english_text(current_text):
                # 检查最近的条目是否都是中文片段（而非完整句子）
                # 策略：只删除短文本（<8字符）的连续中文，保留完整句子
                recent_count = min(10, len(self.subtitle_history))
                fragment_count = 0  # 片段计数

                for i in range(recent_count):
                    entry_text = self._extract_text_content(self.subtitle_history[-(i+1)])

                    # 如果是英文，停止
                    if self._is_english_text(entry_text):
                        break

                    # 如果是中文，判断是否为片段
                    # 片段特征：文本很短（<8字符，排除标点和空格）
                    clean_text = entry_text.replace(" ", "").replace("，", "").replace("。", "").replace("、", "")
                    if len(clean_text) < 8:
                        fragment_count += 1
                    else:
                        # 遇到完整句子，停止（不删除历史完整句子）
                        break

                # 如果之前有连续的中文片段（非完整句子），清理它们
                if fragment_count >= 2:
                    logger.debug(
                        f"🌐 检测到英文翻译,清理前{fragment_count}条中文片段 "
                        f"→ '{current_text[:40]}...'"
                    )
                    # 删除连续的中文片段
                    for _ in range(fragment_count):
                        self.subtitle_history.pop()

                    # 添加英文翻译
                    self.subtitle_history.append(new_entry)
                    # 更新显示后直接返回
                    display_text = self._format_display_text()
                    if self.window and self.text_widget:
                        self.window.after(0, lambda: self._update_text_widget(display_text))
                    return

            # 步骤1: 检查是否为多条合并结果
            merge_count = self._check_merge_candidates(current_text, lookback_count=10)

            if merge_count > 0:
                # 删除最近的merge_count条,添加新的合并文本
                removed_texts = [
                    self._extract_text_content(self.subtitle_history[-i])
                    for i in range(merge_count, 0, -1)
                ]
                logger.debug(
                    f"🔗 合并字幕: {merge_count}条 "
                    f"({' + '.join([t[:5] + '...' if len(t) > 5 else t for t in removed_texts[:3]])}...) "
                    f"→ '{current_text[:30]}...'"
                )

                # 删除旧条目
                for _ in range(merge_count):
                    self.subtitle_history.pop()

                # 添加新的合并文本
                self.subtitle_history.append(new_entry)

            else:
                # 步骤2: 没有多条合并,检查与最后一条的关系
                last_entry = self.subtitle_history[-1]
                last_text = self._extract_text_content(last_entry)

                # 情况1: 完全相同 → 跳过(避免重复)
                if last_text == current_text:
                    logger.debug(f"🔄 字幕重复,跳过: '{current_text[:30]}...'")
                    return

                # 情况2: 文本相似(包含/扩展/高重叠) → 覆盖
                if self._is_text_similar(last_text, current_text):
                    # 保留较长的文本(通常是更完整的版本)
                    if len(current_text) >= len(last_text):
                        # 覆盖最后一条
                        self.subtitle_history[-1] = new_entry
                        logger.debug(f"📝 字幕覆盖: '{last_text[:20]}...' → '{current_text[:20]}...'")
                    else:
                        # 新文本更短,保持原有文本不变
                        logger.debug(f"⏭️  字幕较短,跳过: '{current_text[:30]}...'")
                        return
                else:
                    # 情况3: 完全不同 → 新增
                    self.subtitle_history.append(new_entry)
                    logger.debug(f"➕ 新字幕: '{current_text[:30]}...'")
        else:
            # 第一条字幕,直接添加
            self.subtitle_history.append(new_entry)
            logger.debug(f"🆕 首条字幕: '{current_text[:30]}...'")

        # 构建显示内容（仅展示最近 display_limit 条，排版更友好）
        display_text = self._format_display_text()

        # 线程安全更新
        if self.window and self.text_widget:
            self.window.after(0, lambda: self._update_text_widget(display_text))

    def run(self):
        """运行窗口主循环"""
        logger.info("▶️  字幕窗口主循环启动")
        self.window.mainloop()
        logger.info("⏹️  字幕窗口主循环结束")

    def destroy(self):
        """销毁窗口"""
        if self.window:
            try:
                self.window.quit()
                self.window.destroy()
                logger.info("🛑 字幕窗口已关闭")
            except Exception as e:
                logger.warning(f"⚠️  关闭字幕窗口时出错: {e}")

    def get_raw_history(self) -> list:
        """
        获取原始缓冲区历史（完整的火山引擎输出流）

        Returns:
            原始历史记录列表，每个元素包含:
            - timestamp: 时间戳
            - text: 纯文本内容
            - entry: 格式化后的条目
        """
        return list(self.raw_buffer)

    def get_display_history(self) -> list:
        """
        获取展示缓冲区历史（智能去重后的结果）

        Returns:
            展示历史记录列表
        """
        return list(self.display_buffer)

    def get_stats(self) -> dict:
        """
        获取字幕窗口统计信息

        Returns:
            统计信息字典
        """
        return {
            'width': self.width,
            'height': self.height,
            'font_size': self.current_font_size,
            'opacity': self.opacity,
            'is_visible': self.is_visible,
            'is_large_font': self.is_large_font
        }

    def __repr__(self):
        return (f"SubtitleWindow("
                f"size={self.width}x{self.height}, "
                f"font={self.current_font_size}pt, "
                f"visible={self.is_visible})")


class SubtitleWindowThread:
    """
    字幕窗口线程包装器

    注意: 在 Windows 上,Tkinter 必须在主线程运行
    这个类提供非阻塞的方式启动和管理字幕窗口
    """

    def __init__(self, subtitle_window: SubtitleWindow):
        """
        初始化字幕窗口线程

        Args:
            subtitle_window: SubtitleWindow实例
        """
        self.subtitle_window = subtitle_window
        self.is_running = False

    def start(self):
        """
        启动字幕窗口(非阻塞)

        注意: 此方法会在主线程创建窗口,但不会阻塞
        需要定期调用 process_events() 来处理 UI 事件
        """
        logger.info("🚀 启动字幕窗口...")

        self.subtitle_window.create()
        self.is_running = True

        logger.info("✅ 字幕窗口已启动")

    def stop(self):
        """停止字幕窗口"""
        logger.info("🛑 正在停止字幕窗口...")

        self.is_running = False
        self.subtitle_window.destroy()

        logger.info("✅ 字幕窗口已停止")

    def update_subtitle(self, text: str):
        """
        更新字幕文本

        Args:
            text: 字幕文本
        """
        if self.is_running:
            self.subtitle_window.update_subtitle(text)

    def process_events(self):
        """
        处理 Tkinter 事件队列(非阻塞)

        应该定期调用此方法(例如在主循环中)
        """
        if self.is_running and self.subtitle_window.window:
            try:
                self.subtitle_window.window.update()
            except Exception as e:
                logger.warning(f"⚠️  处理窗口事件时出错: {e}")
