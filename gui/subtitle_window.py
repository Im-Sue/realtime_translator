"""
悬浮字幕窗口模块
显示对方英文翻译成的中文字幕
"""

import tkinter as tk
from tkinter import font, scrolledtext
import threading
import logging
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

        # 历史记录
        self.subtitle_history = deque(maxlen=max_history)

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
            cursor="arrow"  # 鼠标样式
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

    def update_subtitle(self, text: str):
        """
        更新字幕文本(线程安全)
        新字幕会添加到历史记录,显示最近的几条

        Args:
            text: 字幕文本
        """
        if not text or not text.strip():
            return

        # 添加时间戳(可选)
        if self.show_timestamp:
            timestamp = datetime.now().strftime("%H:%M:%S")
            entry = f"[{timestamp}] {text}"
        else:
            entry = text

        # 添加到历史记录
        self.subtitle_history.append(entry)

        # 构建显示内容(最近的N条记录)
        display_text = "\n\n".join(self.subtitle_history)

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
