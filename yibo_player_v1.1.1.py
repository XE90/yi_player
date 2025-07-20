# coding:utf-8
import os
import sys
import random
from PySide6.QtWidgets import (QMainWindow, QApplication, QWidget, QGridLayout,QProgressDialog, 
                               QPushButton, QLabel, QToolButton, QProgressBar, QTextEdit,
                               QLineEdit, QFileDialog, QSlider,QHBoxLayout, QDialog,QCheckBox,
                               QVBoxLayout, QScrollArea, QToolTip, QMessageBox, QSizePolicy)
from PySide6.QtGui import QIcon, QPixmap, QImage
from PySide6.QtCore import QSize, Qt, QUrl, QTimer, QEvent, QThread, Signal, QTranslator, QLocale
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import qtawesome
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
import json  
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import shutil

software_developer = 'Xie.Gavin'
software_version = '1.1.1'
software_date = '2025.07.20'

cwdp = os.getcwd()
#各文件路径
config_path = os.path.abspath(os.path.join(cwdp, fr'_config_'))
music_path = os.path.abspath(os.path.join(cwdp, 'music'))
icon_path = os.path.abspath(os.path.join(cwdp, fr'resource/icon'))
image_path = os.path.abspath(os.path.join(cwdp, fr'resource/image'))
#收藏文件
favorites_file_json = os.path.join(config_path, 'favorites.json')
#E-mail配置文件
email_conf_file_json = os.path.join(config_path, 'Email_config.json')
#软件icon
yibo_icon = os.path.join(icon_path, 'yibo-4.ico')
#专辑图片
picture_1 = os.path.join(image_path, 'ouXiangJuChang.jpg')
picture_2 = os.path.join(image_path, 'shenRuXiaHua.jpg')
picture_3 = os.path.join(image_path, 'huangJiaJu.jpg')
picture_4 = os.path.join(image_path, 'chenBaiQiang.webp')
picture_5 = os.path.join(image_path, 'zhangGuoRong.jfif')

class FeedbackSender(QThread):
    finished = Signal(bool, str)  # 确保信号只定义一次
    
    def __init__(self, smtp_config, subject, body, parent=None):
        super().__init__(parent)
        self.smtp_config = smtp_config
        self.subject = subject
        self.body = body
        self._is_running = True
    
    def run(self):
        try:
            # 使用with语句确保资源正确释放
            with smtplib.SMTP_SSL(self.smtp_config['server'], 
                                self.smtp_config['port'], 
                                timeout=10) as server:
                if not self._is_running:
                    return
                
                server.login(self.smtp_config['username'],
                           self.smtp_config['password'])
                
                if not self._is_running:
                    return
                
                msg = MIMEText(self.body, 'plain', 'utf-8')
                msg['Subject'] = self.subject
                msg['From'] = self.smtp_config['sender']
                msg['To'] = self.smtp_config['recipient']
                
                server.sendmail(
                    self.smtp_config['sender'],
                    self.smtp_config['recipient'],
                    msg.as_string()
                )
                
                # 确保只发送一次成功信号
                if self._is_running:
                    self.finished.emit(True, "反馈已发送成功！感谢您的意见。")
                
        except smtplib.SMTPException as e:
            error_msg = f"邮件发送失败:\n{str(e)}"
            if hasattr(e, 'smtp_error'):
                try:
                    error_msg += f"\nSMTP错误: {e.smtp_error.decode('utf-8')}"
                except:
                    error_msg += "\nSMTP错误: [无法解码错误信息]"
            self.finished.emit(False, error_msg)
        except Exception as e:
            error_msg = f"发生未知错误:\n{str(e)}"
            self.finished.emit(False, error_msg)
        finally:
            # 确保线程退出
            self.quit()
    
    def stop(self):
        """停止线程"""
        self._is_running = False
        self.quit()
        self.wait(2000)  # 等待2秒

class MainUi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"宜播放器 v{software_version}")
        self.setWindowIcon(QIcon(yibo_icon))
        self.translator = QTranslator()
        self.is_muted = False  # 静音状态
        self.volume = 50  # 默认音量
        self.current_theme = 'pink'  # 默认粉色主题
        self.favorites = set()  # 新增：收藏的歌曲集合
        self.playlist = []  # 存储音乐文件路径
        self.filtered_playlist = []
        self.feedback_subject = f"{self.tr("宜播放器")} v{software_version} {self.tr("用户反馈")}"
        # self.smtp_config = {
        # 'server': 'smtp.qq.com',  # 替换为你的SMTP服务器
        # 'port': 465,                  # 通常是587(TLS)或465(SSL)
        # 'username': 'xx@qq.com',  # 替换为发件邮箱
        # 'password': '123',   # 替换为邮箱密码/授权码
        # 'sender': 'xx@qq.com',    # 发件人
        # 'recipient': 'xx1@qq.com'   # 收件人(开发者邮箱)
        # }
        if not os.path.exists(email_conf_file_json):
            print(fr'Not found file: {email_conf_file_json}')
            sys.exit(1)
        with open(email_conf_file_json, 'r') as fr:
            self.smtp_config = json.load(fr)
        self.init_ui()
        # 初始化媒体播放器
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.current_index = -1  # 当前播放索引
        self.song_durations = [0] * len(self.playlist)  # 存储歌曲时长
        self.auto_load_music() # 自动加载music文件夹下的音乐
        self.load_favorites()  # 新增：加载收藏列表
        
        self.lyrics = []  # 存储歌词数据 [(时间, 歌词)]
        self.current_lyric_index = 0  # 当前显示的歌词索引

        self.audio_output.setVolume(self.volume / 100)  # 设置初始音量

        # 添加鼠标拖动窗口所需的变量
        self.drag_position = None
        
        # 连接信号
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.playbackStateChanged.connect(self.update_buttons)
        self.player.mediaStatusChanged.connect(self.handle_media_status) 
        
        # 定时器用于更新进度条
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(1000)  # 每秒更新一次

        #设置进度条滑块信号连接
        self.time_slider.sliderPressed.connect(self.slider_pressed)
        self.time_slider.sliderReleased.connect(self.slider_released)
        self.time_slider.valueChanged.connect(self.slider_moved)

        # 启用点击跳转功能
        self.time_slider.setPageStep(0)  # 允许点击任意位置跳转
        self.time_slider.mousePressEvent = self.slider_mouse_press_event
        self.time_slider.mouseReleaseEvent = self.slider_mouse_release_event
        self.init_theme_ui()
    

    def init_ui(self):
        self.setFixedSize(800,630)
        self.main_widget = QWidget() # 创建窗口主部件
        self.main_layout = QGridLayout() # 创建主部件的网格布局
        self.main_widget.setLayout(self.main_layout) # 设置窗口主部件布局为网格布局
    
        self.left_widget = QWidget() # 创建左侧部件
        self.left_widget.setObjectName('left_widget')
        self.left_layout = QGridLayout() # 创建左侧部件的网格布局层
        self.left_widget.setLayout(self.left_layout) # 设置左侧部件布局为网格
    
        self.right_widget = QWidget() # 创建右侧部件
        self.right_widget.setObjectName('right_widget')
        self.right_layout = QGridLayout()
        self.right_widget.setLayout(self.right_layout) # 设置右侧部件布局为网格
    
        self.main_layout.addWidget(self.left_widget,0,0,12,2) # 左侧部件在第0行第0列，占8行3列
        self.main_layout.addWidget(self.right_widget,0,2,12,10) # 右侧部件在第0行第3列，占8行9列
        self.setCentralWidget(self.main_widget) # 设置窗口主部件


    #左侧菜单的布局中添加按钮部件QPushButton()左侧菜单的按钮、菜单列提示和整个窗口的最小化和关闭按钮。
        self.left_close = QPushButton(qtawesome.icon('fa5s.times', color=self.get_theme_color(), font=18),"") # 关闭按钮
        self.left_close.setIconSize(QSize(20, 20))  # 放大尺寸
        self.left_close.setToolTip('关闭')
        self.left_visit = QPushButton(qtawesome.icon('fa5s.circle', color=self.get_theme_color(), font=18),"") # 空白按钮
        self.left_visit.setIconSize(QSize(20, 20))
        self.left_mini = QPushButton(qtawesome.icon('fa5s.window-minimize', color=self.get_theme_color(), font=18),"") # 最小化按钮
        self.left_mini.setIconSize(QSize(20, 20))
        self.left_mini.setToolTip('最小')
     
        self.left_label_1 = QPushButton("每日推荐")
        self.left_label_1.setObjectName('left_label')
        self.left_label_2 = QPushButton("我的音乐")
        self.left_label_2.setObjectName('left_label')
        self.left_label_3 = QPushButton("软件设置")
        self.left_label_3.setObjectName('left_label')
   
        self.left_button_1 = QPushButton(qtawesome.icon('fa5s.music',color='white'),"网络热歌")
        self.left_button_1.setObjectName('left_button')
        self.left_button_2 = QPushButton(qtawesome.icon('fa5s.broadcast-tower',color='white'),"在线广播")
        self.left_button_2.setObjectName('left_button')
        self.left_button_3 = QPushButton(qtawesome.icon('fa5s.film',color='white'),"热门MV")
        self.left_button_3.setObjectName('left_button')
        self.left_button_4 = QPushButton(qtawesome.icon('fa5s.home',color='white'),"本地音乐")
        self.left_button_4.setObjectName('left_button')
        self.left_button_5 = QPushButton(qtawesome.icon('fa5s.file-audio',color='white'),"歌曲管理")
        self.left_button_5.setObjectName('left_button')
        self.left_button_5.clicked.connect(self.show_music_manager)
        self.left_button_6 = QPushButton(qtawesome.icon('fa5s.heart',color='white'),"我的收藏")
        self.left_button_6.setObjectName('left_button')
        self.left_button_6.clicked.connect(self.show_favorites)
        self.left_button_7 = QPushButton(qtawesome.icon('fa5s.comment',color='white'),"反馈建议")
        self.left_button_7.setObjectName('left_button')
        self.left_button_7.clicked.connect(self.show_feedback_dialog)
        self.left_button_8 = QPushButton(qtawesome.icon('fa5s.palette',color='white'),"主题切换")
        self.left_button_8.setObjectName('left_button')
        self.left_button_8.clicked.connect(self.show_theme_selector)
        # self.left_button_9 = QPushButton(qtawesome.icon('fa5s.question',color='white'),"遇到问题")
        self.left_button_9 = QPushButton(qtawesome.icon('fa5s.info-circle',color='white'),"关于宜播")
        self.left_button_9.setObjectName('left_button')
        self.left_xxx = QPushButton(" ")

        self.left_layout.addWidget(self.left_mini, 0, 0,1,1)
        self.left_layout.addWidget(self.left_close, 0, 2,1,1)
        self.left_layout.addWidget(self.left_visit, 0, 1, 1, 1)
        self.left_layout.addWidget(self.left_label_1,1,0,1,3)
        self.left_layout.addWidget(self.left_button_1, 2, 0,1,3)
        self.left_layout.addWidget(self.left_button_2, 3, 0,1,3)
        self.left_layout.addWidget(self.left_button_3, 4, 0,1,3)
        self.left_layout.addWidget(self.left_label_2, 5, 0,1,3)
        self.left_layout.addWidget(self.left_button_4, 6, 0,1,3)
        self.left_layout.addWidget(self.left_button_5, 7, 0,1,3)
        self.left_layout.addWidget(self.left_button_6, 8, 0,1,3)
        self.left_layout.addWidget(self.left_label_3, 9, 0,1,3)
        self.left_layout.addWidget(self.left_button_7, 10, 0,1,3)
        self.left_layout.addWidget(self.left_button_8, 11, 0,1,3)
        self.left_layout.addWidget(self.left_button_9, 12, 0, 1, 3)


    #搜索模块，有一个文本和一个搜索框
        self.right_bar_widget = QWidget() # 右侧顶部搜索框部件
        self.right_bar_layout = QGridLayout() # 右侧顶部搜索框网格布局
        self.right_bar_widget.setLayout(self.right_bar_layout)
        self.search_icon = QLabel(chr(0xf002) + ' '+'搜索 ')
        self.search_icon.setFont(qtawesome.font('fa5s', 16))
        self.right_bar_widget_search_input = QLineEdit()
        self.right_bar_widget_search_input.setPlaceholderText("输入歌手、歌曲，回车进行搜索")
        self.right_bar_widget_search_input.returnPressed.connect(self.search_music)
     
        self.right_bar_layout.addWidget(self.search_icon,0,0,1,1)
        self.right_bar_layout.addWidget(self.right_bar_widget_search_input,0,1,1,8)

        self.right_layout.addWidget(self.right_bar_widget, 0, 0, 1, 9)


    #推荐音乐模块，在推荐音乐模块中，有一个推荐的标题，和一个横向排列的音乐封面列表
        self.right_recommend_label = QLabel("专属推荐")
        self.right_recommend_label.setObjectName('right_lable')
     
        self.right_recommend_widget = QWidget() # 推荐封面部件
        self.right_recommend_layout = QGridLayout() # 推荐封面网格布局
        self.right_recommend_widget.setLayout(self.right_recommend_layout)
     
        self.recommend_button_1 = QToolButton()
        self.recommend_button_1.setText("偶像剧场") # 设置按钮文本
        self.recommend_button_1.setIcon(QIcon(picture_1)) # 设置按钮图标
        self.recommend_button_1.setIconSize(QSize(100,100)) # 设置图标大小
        self.recommend_button_1.setToolButtonStyle(Qt.ToolButtonTextUnderIcon) # 设置按钮形式为上图下文
     
        self.recommend_button_2 = QToolButton()
        self.recommend_button_2.setText("生如夏花")
        self.recommend_button_2.setIcon(QIcon(picture_2))
        self.recommend_button_2.setIconSize(QSize(100, 100))
        self.recommend_button_2.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
     
        self.recommend_button_3 = QToolButton()
        self.recommend_button_3.setText("黄家驹")
        self.recommend_button_3.setIcon(QIcon(picture_3))
        self.recommend_button_3.setIconSize(QSize(100, 100))
        self.recommend_button_3.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
     
        self.recommend_button_4 = QToolButton()
        self.recommend_button_4.setText("陈百强")
        self.recommend_button_4.setIcon(QIcon(picture_4))
        self.recommend_button_4.setIconSize(QSize(100, 100))
        self.recommend_button_4.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
     
        self.recommend_button_5 = QToolButton()
        self.recommend_button_5.setText("张国荣")
        self.recommend_button_5.setIcon(QIcon(picture_5))
        self.recommend_button_5.setIconSize(QSize(100, 100))
        self.recommend_button_5.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
     
        self.right_recommend_layout.addWidget(self.recommend_button_1,0,0)
        self.right_recommend_layout.addWidget(self.recommend_button_2,0,1)
        self.right_recommend_layout.addWidget(self.recommend_button_3, 0, 2)
        self.right_recommend_layout.addWidget(self.recommend_button_4, 0, 3)
        self.right_recommend_layout.addWidget(self.recommend_button_5, 0, 4)
     
        self.right_layout.addWidget(self.right_recommend_label, 1, 0, 1, 9)
        self.right_layout.addWidget(self.right_recommend_widget, 2, 0, 2, 9)

     
    #创建音乐列表模块和音乐歌单模块。音乐列表模块和音乐歌单模块都有一个标题和一个小部件来容纳具体的内容。
        self.right_newsong_lable = QLabel("歌曲清单")
        self.right_newsong_lable.setObjectName('right_lable')

        # 创建滚动区域
        self.song_scroll = QScrollArea()
        self.song_scroll.setWidgetResizable(True)
        # self.song_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示滚动条
        self.song_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 按需显示滚动条
        self.song_scroll_content = QWidget()
        self.song_scroll_layout = QVBoxLayout(self.song_scroll_content)
        self.song_scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.song_scroll_layout.setSpacing(0)
        self.song_scroll_layout.setAlignment(Qt.AlignTop)  # 确保内容向上对齐
        self.song_scroll.setWidget(self.song_scroll_content)   

        # 设置滚动区域无边框
        self.song_scroll.setStyleSheet("QScrollArea { border: none; }")
        self.song_scroll_content.setStyleSheet('''
            QWidget {
                background: white;
            }
        ''')
        
        # 存储歌曲按钮和时长标签的列表
        self.song_buttons = []
        self.song_duration_labels = []
        
        self.right_layout.addWidget(self.right_newsong_lable, 4, 0, 1, 5)
        self.right_layout.addWidget(self.song_scroll, 5, 0, 4, 5)  # 增加行数
     
        self.right_playlist_lable = QLabel("当前播放")
        self.right_playlist_lable.setObjectName('right_lable')
     
        # self.right_newsong_widget = QWidget() # 最新歌曲部件
        self.right_newsong_layout = QGridLayout() # 最新歌曲部件网格布局
        # self.right_newsong_widget.setLayout(self.right_newsong_layout)
        
        # 创建歌曲列表按钮
        self.song_buttons = []
        self.song_duration_labels = []  # 存储时长标签
        for i in range(6):
            # 创建水平布局容器
            song_container = QWidget()
            song_layout = QGridLayout(song_container)
            song_layout.setContentsMargins(0, 0, 0, 0)
            
            btn = QPushButton("")
            btn.setProperty('index', i)  # 存储索引
            btn.clicked.connect(self.play_selected_song)
            
            duration_label = QLabel("")
            duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            song_layout.addWidget(btn, 0, 0)
            song_layout.addWidget(duration_label, 0, 1)
            
            self.right_newsong_layout.addWidget(song_container, i, 1)
            self.song_buttons.append(btn)
            self.song_duration_labels.append(duration_label)
     
        self.right_playlist_widget = QWidget() # 播放歌单部件
        self.right_playlist_layout = QGridLayout() # 播放歌单网格布局
        self.right_playlist_widget.setLayout(self.right_playlist_layout)

        self.right_layout.addWidget(self.right_newsong_lable, 4, 0, 1, 5)
        self.right_layout.addWidget(self.right_playlist_lable, 4, 5, 1, 4)
        # self.right_layout.addWidget(self.right_newsong_widget, 5, 0, 1, 5)
        # self.right_layout.addWidget(self.song_scroll_content, 5, 0, 1, 5)
        self.right_layout.addWidget(self.right_playlist_widget, 5, 5, 1, 4)

        #音乐播放进度条和音乐播放控制按钮组
        #显示正在播放的歌曲
        self.song_name_label = QLabel("未播放")
        self.song_name_label.setAlignment(Qt.AlignCenter)
        self.song_name_label.setStyleSheet("""
            font-size: 12px; 
            color: #F76677;
            qproperty-alignment: AlignCenter;
        """)

        # 创建歌词显示标签（三行：上一句、当前句、下一句）
        self.lyrics_label = QLabel("")
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_label.setStyleSheet("""
            font-size: 12px; 
            color: #F76677;
            qproperty-alignment: AlignCenter;
        """)
        self.lyrics_label.setWordWrap(True)  # 允许自动换行
        # self.lyrics_label.setFixedHeight(50)  # 增加高度以显示三行歌词

        # 创建一个垂直布局容器来放置歌曲名称和歌词
        lyrics_container = QWidget()
        lyrics_layout = QVBoxLayout(lyrics_container)
        lyrics_layout.setContentsMargins(0, 0, 0, 0)
        lyrics_layout.setSpacing(5)
        lyrics_layout.addWidget(self.song_name_label)
        lyrics_layout.addWidget(self.lyrics_label)
        
        # self.right_layout.addWidget(lyrics_container, 9, 0, 1, 9)
        self.right_layout.addWidget(lyrics_container, 5, 4, 1, 5)
        
        # 创建时间显示和进度条控制部件
        self.time_control_widget = QWidget()
        self.time_control_layout = QGridLayout(self.time_control_widget)
        self.time_control_layout.setContentsMargins(0, 0, 0, 0)
        
        self.current_time_label = QLabel("00:00")
        self.total_time_label = QLabel("00:00")
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(0, 100)
        self.time_slider.setFixedHeight(3)
        self.time_slider.sliderMoved.connect(self.seek_position)
        self.time_slider.installEventFilter(self)  # 添加事件过滤器
        
        self.time_control_layout.addWidget(self.current_time_label, 0, 0)
        self.time_control_layout.addWidget(self.time_slider, 0, 1)
        self.time_control_layout.addWidget(self.total_time_label, 0, 2)
     
        self.right_playconsole_widget = QWidget() # 播放控制部件
        self.right_playconsole_layout = QGridLayout() # 播放控制部件网格布局层
        self.right_playconsole_widget.setLayout(self.right_playconsole_layout)

        # 在播放控制部件中添加专辑封面
        self.album_art_label = QLabel()
        self.album_art_label.setFixedSize(60, 60)  # 设置固定大小
        self.album_art_label.setStyleSheet("""
            QLabel {
                border: None;
                border-radius: 5px;
                background: white;
            }
        """)

        # 默认专辑封面（如果没有专辑图则显示默认图标）
        self.album_default_icon = qtawesome.icon('fa5s.compact-disc', color=self.get_theme_color())
        pixmap = self.album_default_icon.pixmap(60, 60)
        self.album_art_label.setPixmap(pixmap)

        self.console_button_1 = QPushButton(qtawesome.icon('fa5s.backward', color='#F76677'), "")
        self.console_button_1.setToolTip("上一曲")
        self.console_button_2 = QPushButton(qtawesome.icon('fa5s.forward', color='#F76677'), "")
        self.console_button_2.setToolTip("下一曲")
        self.console_button_3 = QPushButton(qtawesome.icon('fa5s.play', color='#F76677', font=18), "")
        self.console_button_3.setToolTip("播放/暂停")
        self.console_button_3.setIconSize(QSize(30, 30))

        self.play_mode = 0  # 0-顺序播放, 1-循环播放, 2-单曲循环，3-随机播放
        self.console_button_mode = QPushButton(qtawesome.icon('fa5s.list-ol', color='#F76677'), "")
        self.console_button_mode.setToolTip("顺序播放")
        self.console_button_mode.clicked.connect(self.toggle_play_mode)


        # 在播放控制部件中添加音量控制
        self.volume_button = QPushButton(qtawesome.icon('fa5s.volume-up', color='#F76677'), "")
        self.volume_button.setToolTip(self.tr("静音"))
        self.volume_button.clicked.connect(self.toggle_mute)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.volume)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setStyleSheet("""
            QSlider::handle:horizontal {
                background: pink;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -8px 0; /* 使滑块超出轨道 */
            }
        """)
        self.volume_slider.valueChanged.connect(
            lambda value: self.volume_slider.setToolTip(self.tr("音量: {}").format(f"{value}%"))
        )

        # 添加到布局中
        self.right_playconsole_layout.addWidget(self.volume_button, 0, 5)
        self.right_playconsole_layout.addWidget(self.volume_slider, 0, 6)
                
        # 添加到布局中
        self.right_playconsole_layout.addWidget(self.console_button_mode, 0, 4)
        
        # 连接按钮信号
        self.console_button_1.clicked.connect(self.play_previous)
        self.console_button_2.clicked.connect(self.play_next)
        self.console_button_3.clicked.connect(self.toggle_play_pause)
        self.left_button_4.clicked.connect(self.load_local_music)  # 本地音乐按钮

        self.right_playconsole_layout.addWidget(self.album_art_label, 0, 0)  # 添加到第一列
        self.right_playconsole_layout.addWidget(self.console_button_1, 0, 1)  # 上一曲按钮移到第二列
        self.right_playconsole_layout.addWidget(self.console_button_2, 0, 3)  # 下一曲按钮
        self.right_playconsole_layout.addWidget(self.console_button_3, 0, 2)  # 播放/暂停按钮
     
        self.right_playconsole_layout.setAlignment(Qt.AlignCenter) # 设置布局内部件居中显示
     
        # self.right_layout.addWidget(self.right_process_bar, 9, 0, 1, 9)
        self.right_layout.addWidget(self.time_control_widget, 11, 0, 1, 9)
        # self.right_layout.addWidget(self.now_playing_label, 11, 0, 1, 9)
        self.right_layout.addWidget(self.right_playconsole_widget, 12, 0, 1, 9)

        #窗口控制按钮
        self.left_close.setFixedSize(25,25) # 设置关闭按钮的大小
        self.left_visit.setFixedSize(25, 25) # 设置按钮大小
        self.left_mini.setFixedSize(25, 25) # 设置最小化按钮大小

        # 连接窗口控制按钮
        self.left_close.clicked.connect(self.showCloseDialog)
        self.left_mini.clicked.connect(self.showMinimized)

        #将左侧菜单中的按钮和文字颜色设置为白色，并且将按钮的边框去掉，在left_widget中设置qss样式
        self.left_widget.setStyleSheet('''
         QPushButton{border:none;color:white;}
         QPushButton#left_label{
         border:none;
         border-bottom:1px solid white;
         font-size:18px;
         font-weight:700;
         font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
         }
         QPushButton#left_button:hover{border-left:4px solid red;font-weight:700;}
            ''')
        
        #设置搜索框为圆棱角
        self.right_bar_widget_search_input.setStyleSheet(
         '''QLineEdit{
            border:1px solid gray;
            width:300px;
            border-radius:10px;
            padding:2px 4px;
         }''')
        
        #右侧的部件的右上角和右下角需要先行处理为圆角的，背景设置为白色。
        #对推荐模块、音乐列表模块和音乐歌单模块的标题对其字体进行放大处理
        self.right_widget.setStyleSheet('''
            QWidget#right_widget{
            color:#232C51;
            background:white;
            border-top:1px solid darkGray;
            border-bottom:1px solid darkGray;
            border-right:1px solid darkGray;
            border-top-right-radius:10px;
            border-bottom-right-radius:10px;
            }
            QLabel#right_lable{
            border:none;
            font-size:16px;
            font-weight:700;
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
            }
         ''')   
        
        #推荐模块和歌单模块
        self.right_recommend_widget.setStyleSheet(
         '''
         QToolButton{border:none;}
         QToolButton:hover{border-bottom:2px solid #F76677;}
         ''')
        self.right_playlist_widget.setStyleSheet(
         '''
         QToolButton{border:none;}
         QToolButton:hover{border-bottom:2px solid #F76677;}
         ''')
        
        #音乐列表，去除边框，修改字体和颜色等 LightGray
        self.song_scroll_content.setStyleSheet('''
            QWidget {
                background: white;
            }
            QPushButton {
                border: none;
                color: gray;
                font-size: 12px;
                height: 40px;
                padding-left: 5px;
                padding-right: 10px;
            }
            QPushButton:hover {
                color: black;
                border: 1px solid #F3F3F5;
                border-radius: 10px;
                background: LightGray;
            }
            QLabel {
                font-size: 10px;
                color: gray;
                padding-right: 5px;
            }
        ''')
        
        #播放进度条的样色设置为浅红色，然后去除播放控制按钮的边框
        # self.right_process_bar.setStyleSheet('''
        #     QProgressBar::chunk {
        #     background-color: #F76677;
        #     }
        #  ''')
        self.right_playconsole_widget.setStyleSheet('''
            QPushButton{
            border:none;
            }
         ''')
        
        #时间滑块样式
        self.time_slider.setStyleSheet('''
            QSlider::groove:horizontal {
            height: 3px;
            background: lightgray;
            }
            QSlider::handle:horizontal {
            width: 8px;
            height: 8px;
            background: #F76677;
            margin: -2px 0;
            border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
            background: #F76677;
            }
        ''')
        
        #图形界面的窗口背景设为透明
        self.setWindowOpacity(0.95) # 设置窗口透明度
        self.setAttribute(Qt.WA_TranslucentBackground) # 设置窗口背景透明

        #去除窗口边框
        self.setWindowFlag(Qt.FramelessWindowHint) # 隐藏边框

        #为了避免隐藏窗口边框后，左侧部件没有背景颜色和边框显示，对左侧部件添加QSS属性
        self.main_widget.setStyleSheet('''
         QWidget#left_widget{
         background:gray;
         border-top:1px solid white;
         border-bottom:1px solid white;
         border-left:1px solid white;
         border-top-left-radius:10px;
         border-bottom-left-radius:10px;
         }
         ''')
        
        #图形界面中左侧部件和右侧部件中有一条缝隙，通过设置布局内部件的间隙来把那条缝隙去除掉
        self.main_layout.setSpacing(0)

        #设置ToolTip风格
        self.set_tool_tip_style()

        #初始化‘关于’页面
        self.init_about_ui()

    def set_tool_tip_style(self):
        # 使用全局样式设置，只针对QToolTip类
        self.setStyleSheet('''
            QToolTip {
                border: none;
                border-radius: 8px;
                background-color: %s;
                color: white;
                padding: 5px;
            }
        ''' % self.get_theme_color())

    def init_about_ui(self):
        # 创建关于页面
        self.about_widget = QWidget()
        self.about_widget.setObjectName('about_widget')  # 添加对象名用于样式设置
        self.about_widget.hide()  # 初始隐藏
        self.about_layout = QVBoxLayout(self.about_widget)
        
        # 设置关于页面背景样式（与右侧部件相同）
        self.about_widget.setStyleSheet('''
            QWidget#about_widget{
                color:#232C51;
                background:white;
                border-top:1px solid darkGray;
                border-bottom:1px solid darkGray;
                border-right:1px solid darkGray;
                border-radius:10px;
            }
        ''')
        
        # 关于页面内容
        self.about_title = QLabel("宜播放器")
        # theme_title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {self.get_theme_color()};")
        self.about_title.setStyleSheet(f"font-size: 24px; font-weight: bold;color: {self.get_theme_color()};")
        self.about_title.setAlignment(Qt.AlignCenter)
        
        self.version_label = QLabel(f"版本: {software_version}")
        self.date_label = QLabel(f"发布日期: {software_date}")
        self.developer_label = QLabel(f"开发者: {software_developer}")
        
        # 设置样式
        for label in [self.version_label, self.date_label, self.developer_label]:
            label.setStyleSheet("font-size: 16px; margin: 10px 0;")
            label.setAlignment(Qt.AlignCenter)
        
        # 返回按钮
        self.about_page_back_button = QPushButton(qtawesome.icon('fa5s.arrow-left',color=self.get_theme_color()), "")
        self.about_page_back_button.setText("返回主界面")
        self.about_page_back_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 14px;
                color: {self.get_theme_color()};
                border: 1px solid {self.get_theme_color()};
                border-radius: 5px;
                padding: 5px 10px;
                margin-top: 20px;
            }}
            QPushButton:hover {{
                background: {self.get_theme_color()};
                color: white;
            }}
        """)
        self.about_page_back_button.clicked.connect(self.show_main_interface)
        
        # 添加到布局
        self.about_layout.addStretch(1)
        self.about_layout.addWidget(self.about_title)
        self.about_layout.addWidget(self.version_label)
        self.about_layout.addWidget(self.date_label)
        self.about_layout.addWidget(self.developer_label)
        self.about_layout.addWidget(self.about_page_back_button, 0, Qt.AlignCenter)
        self.about_layout.addStretch(1)
        
        # 将关于页面添加到主布局
        self.main_layout.addWidget(self.about_widget, 0, 0, 12, 12)
        
        # 连接关于按钮信号
        self.left_button_9.clicked.connect(self.show_about_page)

    # 新增：加载收藏列表
    def load_favorites(self):
        """从文件加载收藏列表"""
        if os.path.exists(favorites_file_json):
            try:
                with open(favorites_file_json, 'r', encoding='utf-8') as f:
                    self.favorites = set(json.load(f))
            except:
                self.favorites = set()
    
    # 新增：保存收藏列表
    def save_favorites(self):
        """保存收藏列表到文件"""
        with open(favorites_file_json, 'w', encoding='utf-8') as f:
            json.dump(list(self.favorites), f, ensure_ascii=False)
    
    # 新增：切换收藏状态
    def toggle_favorite(self, song_path):
        """切换歌曲的收藏状态"""
        if song_path in self.favorites:
            self.favorites.remove(song_path)
        else:
            self.favorites.add(song_path)
        self.save_favorites()
        self.update_song_list(self.filtered_playlist if hasattr(self, 'filtered_playlist') and self.filtered_playlist else self.playlist)
    
    # 新增：切换收藏状态处理
    def toggle_favorite_status(self):
        """处理收藏按钮点击"""
        sender = self.sender()
        index = sender.property('index')
        # 确保使用正确的播放列表
        target_playlist = self.filtered_playlist if hasattr(self, 'filtered_playlist') and self.filtered_playlist else self.playlist
        
        if 0 <= index < len(target_playlist):
            song_path = target_playlist[index]
            self.toggle_favorite(song_path)
            # 更新按钮图标
            if song_path in self.favorites:
                sender.setIcon(qtawesome.icon('fa5s.heart', color=self.get_theme_color()))
                sender.setToolTip(self.tr("取消收藏"))
            else:
                sender.setIcon(qtawesome.icon('fa5s.heart', color='gray'))
                sender.setToolTip(self.tr("添加到收藏"))

    # 新增：显示收藏歌曲
    def show_favorites(self):
        """显示收藏的歌曲"""
        self.show_favorite_title = self.tr("提示")
        self.show_favorite_msg1 = self.tr("暂无收藏歌曲")
        self.show_favorite_msg2 = self.tr("收藏的歌曲不在当前播放列表中")
        if not self.favorites:
            QMessageBox.information(self, self.show_favorite_title, self.show_favorite_msg1 )
            return
        
        # 过滤出收藏的歌曲
        self.filtered_playlist = [song for song in self.playlist if song in self.favorites]
        
        if not self.filtered_playlist:
            QMessageBox.information(self, self.show_favorite_title, self.show_favorite_msg2)
            return
        
        # 更新歌曲列表显示
        self.update_song_list(self.filtered_playlist)

    def show_feedback_dialog(self):
        """显示反馈对话框"""
        self.feedback_dialog = QDialog(self)
        self.feedback_dialog.setWindowTitle(self.tr("反馈建议"))
        self.feedback_dialog.setFixedSize(450, 300)
        
        self.feedback_layout = QVBoxLayout(self.feedback_dialog)
        
        # 添加说明标签
        self.feedback_label = QLabel(self.tr("请填写您的反馈意见，我们将尽快处理:"))
        self.feedback_layout.addWidget(self.feedback_label)
        
        # 添加文本框
        self.feedback_text = QTextEdit()
        self.feedback_text.setPlaceholderText(self.tr("请输入您的反馈内容..."))
        self.feedback_layout.addWidget(self.feedback_text)
        
        # 添加邮箱输入框
        self.user_email = QLineEdit()
        self.user_email.setPlaceholderText(self.tr("您的邮箱(可选)"))
        self.feedback_layout.addWidget(self.user_email)
        
        # 添加按钮布局
        button_layout = QHBoxLayout()
        
        # 发送按钮
        self.feedback_send_btn = QPushButton(self.tr("发送反馈"))
        self.feedback_send_btn.clicked.connect(lambda: self.send_feedback(self.feedback_dialog))
        self.feedback_send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.get_theme_color()};
                color: white;
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                background: white;
                color: {self.get_theme_color()};
                border: 1px solid {self.get_theme_color()};
            }}
        """)
        
        # 取消按钮
        self.feedback_cancel_btn = QPushButton(self.tr("取消"))
        self.feedback_cancel_btn.clicked.connect(self.feedback_dialog.reject)
        self.feedback_cancel_btn.setStyleSheet("""
            QPushButton {
                background: #ccc;
                color: black;
                border-radius: 5px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background: #aaa;
            }
        """)
        
        button_layout.addWidget(self.feedback_send_btn)
        button_layout.addWidget(self.feedback_cancel_btn)
        self.feedback_layout.addLayout(button_layout)
        
        self.feedback_dialog.exec_()

    def send_feedback(self, dialog):
        feedback_content = self.feedback_text.toPlainText().strip()
        user_email = self.user_email.text().strip()
        
        if not feedback_content:
            QMessageBox.warning(self, "提示", "反馈内容不能为空！")
            return
        
        body = f"""用户反馈内容:
        {feedback_content}

        用户邮箱: {user_email if user_email else "未提供"}
        软件版本: 宜播放器 {software_version}
        系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # 创建进度对话框
        self.sending_dialog = QProgressDialog("正在发送反馈...", "取消", 0, 0, self)
        self.sending_dialog.setWindowTitle("请稍候")
        self.sending_dialog.setWindowModality(Qt.WindowModal)
        self.sending_dialog.setCancelButton(None)  # 先禁用取消按钮
        
        # 创建发送线程
        self.feedback_thread = FeedbackSender(
            self.smtp_config,
            self.feedback_subject,
            body
        )
        
        # 连接信号
        self.feedback_thread.finished.connect(
            lambda success, msg: self.handle_feedback_result(success, msg, dialog)
        )
        
        # 线程结束后自动删除
        self.feedback_thread.finished.connect(self.feedback_thread.deleteLater)
        
        # 启动线程
        self.feedback_thread.start()
        
        # 显示进度对话框
        self.sending_dialog.show()

    def handle_feedback_result(self, success, message, dialog):
        """处理反馈结果"""
        try:
            if hasattr(self, 'sending_dialog'):
                self.sending_dialog.close()
            
            # 防止重复处理
            if getattr(self, '_feedback_processed', False):
                return
            self._feedback_processed = True
            
            if success:
                QMessageBox.information(self, "成功", message)
                dialog.accept()
            else:
                QMessageBox.critical(self, "发送失败", message)
                
            # 确保线程停止
            if hasattr(self, 'feedback_thread'):
                self.feedback_thread.stop()
        except Exception as e:
            print(f"处理反馈结果时出错: {e}")
        finally:
            # 重置处理标志
            self._feedback_processed = False

    def handle_send_timeout(self, dialog):
        """处理发送超时"""
        if hasattr(self, 'feedback_thread') and self.feedback_thread.isRunning():
            self.feedback_thread.stop()
            self.feedback_thread.quit()
            self.feedback_thread.wait(1000)  # 等待线程结束
        
        if hasattr(self, 'sending_dialog'):
            self.sending_dialog.close()
        
        QMessageBox.warning(self, "超时", "发送反馈超时，请检查网络连接后重试。")
        dialog.reject()

    def cancel_feedback_send(self, sending_dialog, timeout_timer, thread):
        """取消反馈发送"""
        if hasattr(self, 'timeout_timer'):
            self.timeout_timer.stop()
        
        if hasattr(self, 'feedback_thread') and self.feedback_thread.isRunning():
            self.feedback_thread.stop()
            self.feedback_thread.quit()
            self.feedback_thread.wait(1000)  # 等待线程结束
        
        if hasattr(self, 'sending_dialog'):
            self.sending_dialog.close()
        
        QMessageBox.information(self, "取消", "反馈发送已取消")

    def handle_send_timeout(self, sending_dialog, parent_dialog):
        """处理发送超时"""
        sending_dialog.close()
        QMessageBox.warning(self, "超时", "发送反馈超时，请检查网络连接后重试。")
        parent_dialog.reject()

    def cancel_feedback_send(self, sending_dialog, timeout_timer, thread):
        """取消反馈发送"""
        timeout_timer.stop()
        sending_dialog.close()
        # 无法真正停止SMTP线程，但可以关闭对话框
        QMessageBox.information(self, "取消", "反馈发送已取消")

    def show_about_page(self):
        """显示关于页面"""
        self.left_widget.hide()
        self.right_widget.hide()
        self.about_widget.show()

    def show_main_interface(self):
        """显示主界面"""
        self.theme_widget.hide()
        self.about_widget.hide()
        self.left_widget.show()
        self.right_widget.show()

    def init_theme_ui(self):
        """初始化主题选择界面"""
        self.theme_widget = QWidget()
        self.theme_widget.setObjectName('theme_widget')
        self.theme_widget.hide()  # 初始隐藏
        self.theme_layout = QVBoxLayout(self.theme_widget)
        
        # 设置主题页面背景样式
        self.theme_widget.setStyleSheet('''
            QWidget#theme_widget{
                color:#232C51;
                background:white;
                border-top:1px solid darkGray;
                border-bottom:1px solid darkGray;
                border-right:1px solid darkGray;
                border-radius:10px;
            }
            QPushButton {
                font-size: 16px;
                padding: 10px;
                margin: 5px;
                border-radius: 5px;
                border: 2px solid #ddd;
            }
        ''')
        self.theme_color_layout = QHBoxLayout()
        # 主题选择标题
        self.theme_title_color = QLabel(self.tr("选择主题颜色:"))
        self.theme_title_color.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {self.get_theme_color()};")
        self.theme_title_color.setAlignment(Qt.AlignCenter)
        
        # 创建主题颜色按钮
        self.pink_theme_btn = QPushButton("粉色")
        self.pink_theme_btn.setFixedWidth(100)
        # self.pink_theme_btn.setStyleSheet("background: #F76677; color: white;")
        self.pink_theme_btn.setStyleSheet("""
                                          QPushButton {
                                          background:white; color: #F76677}
                                          QPushButton:hover {
                                          background: #F76677; color: white;
                                          }
                                          """)
        self.pink_theme_btn.clicked.connect(lambda: self.apply_theme('pink'))
        
        self.blue_theme_btn = QPushButton("蓝色")
        self.blue_theme_btn.setFixedWidth(100)
        self.blue_theme_btn.setStyleSheet("""
                                          QPushButton {
                                          background:white; color: #6D8CEB}
                                          QPushButton:hover {
                                          background: #6D8CEB; color: white;
                                          }
                                          """)
        self.blue_theme_btn.clicked.connect(lambda: self.apply_theme('blue'))
        
        self.green_theme_btn = QPushButton("淡绿色")
        self.green_theme_btn.setFixedWidth(100)
        # self.green_theme_btn.setStyleSheet("background: #6DDF6D; color: white;")
        self.green_theme_btn.setStyleSheet("""
                                          QPushButton {
                                          background:white; color: #6DDF6D}
                                          QPushButton:hover {
                                          background: #6DDF6D; color: white;
                                          }
                                          """)
        self.green_theme_btn.clicked.connect(lambda: self.apply_theme('green'))
        
        self.orange_theme_btn = QPushButton("橘色")
        self.orange_theme_btn.setFixedWidth(100)
        # self.orange_theme_btn.setStyleSheet("background: #FFA500; color: white;")
        self.orange_theme_btn.setStyleSheet("""
                                          QPushButton {
                                          background:white; color: #FFA500}
                                          QPushButton:hover {
                                          background: #FFA500; color: white;
                                          }
                                          """)
        self.orange_theme_btn.clicked.connect(lambda: self.apply_theme('orange'))
        
        self.purple_theme_btn = QPushButton("紫色")
        self.purple_theme_btn.setFixedWidth(100)
        # self.purple_theme_btn.setStyleSheet("background: #9B59B6; color: white;")
        self.purple_theme_btn.setStyleSheet("""
                                          QPushButton {
                                          background:white; color: #9B59B6}
                                          QPushButton:hover {
                                          background: #9B59B6; color: white;
                                          }
                                          """)
        self.purple_theme_btn.clicked.connect(lambda: self.apply_theme('purple'))
        
        # 返回按钮
        self.theme_page_back_button = QPushButton(qtawesome.icon('fa5s.arrow-left', color=self.get_theme_color()), "返回主界面")
        self.theme_page_back_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 14px;
                color: {self.get_theme_color()};
                border: 1px solid {self.get_theme_color()};
                border-radius: 5px;
                padding: 5px 10px;
                margin-top: 20px;
            }}
            QPushButton:hover {{
                background: {self.get_theme_color()};
                color: white;
            }}
        """)
        self.theme_page_back_button.clicked.connect(self.show_main_interface)

        #添加主题语言布局
        self.theme_language_layout = QHBoxLayout()

         # 主题选择语言标题
        self.theme_title_language = QLabel(self.tr("选择主题语言:"))
        self.theme_title_language.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {self.get_theme_color()};")
        self.theme_title_language.setAlignment(Qt.AlignCenter)
        
        # 创建主题语言按钮
        self.chinese_theme_btn = QPushButton("汉语")
        self.chinese_theme_btn.setFixedWidth(100)
        self.chinese_theme_btn.setStyleSheet(f"""
                                          QPushButton {{
                                          background:white; 
                                          color: {self.get_theme_color()};
                                          }}
                                          QPushButton:hover {{
                                          background: {self.get_theme_color()}; 
                                          color: white;
                                          }}
                                          """)
        self.chinese_theme_btn.clicked.connect(lambda: self.change_language('zh'))
        
        self.english_theme_btn = QPushButton("英语")
        self.english_theme_btn.setFixedWidth(100)
        self.english_theme_btn.setStyleSheet(f"""
                                          QPushButton {{
                                          background:white; 
                                          color: {self.get_theme_color()};
                                          }}
                                          QPushButton:hover {{
                                          background: {self.get_theme_color()}; 
                                          color: white;
                                          }}
                                          """)
        self.english_theme_btn.clicked.connect(lambda: self.change_language('en'))
        
        # 添加到布局
        self.theme_layout.addStretch(1)
        # self.theme_layout.addWidget(theme_title)
        # self.theme_layout.addWidget(self.pink_theme_btn, 0, Qt.AlignCenter)
        # self.theme_layout.addWidget(self.blue_theme_btn, 0, Qt.AlignCenter)
        # self.theme_layout.addWidget(self.green_theme_btn, 0, Qt.AlignCenter)
        # self.theme_layout.addWidget(self.orange_theme_btn, 0, Qt.AlignCenter)
        # self.theme_layout.addWidget(self.purple_theme_btn, 0, Qt.AlignCenter)
        self.theme_color_layout.addWidget(self.theme_title_color)
        self.theme_color_layout.addWidget(self.pink_theme_btn, 0, Qt.AlignCenter)
        self.theme_color_layout.addWidget(self.blue_theme_btn, 0, Qt.AlignCenter)
        self.theme_color_layout.addWidget(self.green_theme_btn, 0, Qt.AlignCenter)
        self.theme_color_layout.addWidget(self.orange_theme_btn, 0, Qt.AlignCenter)
        self.theme_color_layout.addWidget(self.purple_theme_btn, 0, Qt.AlignCenter)
        self.theme_layout.addLayout(self.theme_color_layout)

        self.theme_language_layout.addWidget(self.theme_title_language, 1, Qt.AlignLeft)
        self.theme_language_layout.addWidget(self.chinese_theme_btn, 1,  Qt.AlignLeft)
        self.theme_language_layout.addWidget(self.english_theme_btn, 1,  Qt.AlignLeft)
        self.theme_layout.addLayout(self.theme_language_layout)

        self.theme_layout.addWidget(self.theme_page_back_button, 0, Qt.AlignCenter)
        self.theme_layout.addStretch(1)
        
        # 将主题页面添加到主布局
        self.main_layout.addWidget(self.theme_widget, 0, 0, 12, 12)

    def change_language(self, lang_code):
        """切换语言"""
        # 移除旧的翻译
        QApplication.instance().removeTranslator(self.translator)
        
        # 加载新的翻译文件
        if lang_code == 'zh':
            if self.translator.load('yiplayer_zh.qm', 'translations'):
                QApplication.instance().installTranslator(self.translator)
        elif lang_code == 'en':
            if self.translator.load('yiplayer_en_US.qm', 'translations'):
                QApplication.instance().installTranslator(self.translator)
        
        # 重新翻译所有界面
        self.retranslateUi()
        self.show_main_interface()

    def retranslateUi(self):
        """重新翻译所有界面文本"""
        # 主窗口标题
        self.setWindowTitle(self.tr("宜播放器: {}").format(f"v{software_version}"))
        
        # 左侧菜单
        self.left_close.setToolTip(self.tr("关闭"))
        self.left_mini.setToolTip(self.tr("最小"))
        self.left_label_1.setText(self.tr("每日推荐"))
        self.left_label_2.setText(self.tr("我的音乐"))
        self.left_label_3.setText(self.tr("软件设置"))
        self.left_button_1.setText(self.tr("网络热歌"))
        self.left_button_2.setText(self.tr("在线广播"))
        self.left_button_3.setText(self.tr("热门MV"))
        self.left_button_4.setText(self.tr("本地音乐"))
        self.left_button_5.setText(self.tr("歌曲管理"))
        self.left_button_6.setText(self.tr("我的收藏"))
        self.left_button_7.setText(self.tr("反馈建议"))
        self.left_button_8.setText(self.tr("主题切换"))
        self.left_button_9.setText(self.tr("关于宜播"))
        
        # 搜索框
        self.search_icon.setText(chr(0xf002) + ' ' + self.tr("搜索"))
        self.right_bar_widget_search_input.setPlaceholderText(self.tr("输入歌手、歌曲，回车进行搜索"))
        
        # 右侧标签
        self.right_recommend_label.setText(self.tr("专属推荐"))
        self.right_newsong_lable.setText(self.tr("歌曲清单"))
        self.right_playlist_lable.setText(self.tr("当前播放"))
        
        # 控制按钮
        self.console_button_1.setToolTip(self.tr("上一曲"))
        self.console_button_2.setToolTip(self.tr("下一曲"))
        self.console_button_3.setToolTip(self.tr("播放/暂停"))
        self.console_button_mode.setToolTip(self.tr("顺序播放"))
        
        # 主题界面
        self.theme_title_color.setText(self.tr("选择主题颜色:"))
        self.theme_title_language.setText(self.tr("选择主题语言:"))
        self.pink_theme_btn.setText(self.tr("粉色"))
        self.blue_theme_btn.setText(self.tr("蓝色"))
        self.green_theme_btn.setText(self.tr("淡绿色"))
        self.orange_theme_btn.setText(self.tr("橘色"))
        self.purple_theme_btn.setText(self.tr("紫色"))
        self.chinese_theme_btn.setText(self.tr("汉语"))
        self.english_theme_btn.setText(self.tr("英语"))
        self.theme_page_back_button.setText(self.tr("返回主界面"))

        # 歌曲管理对话框（如果已创建）
        if hasattr(self, 'music_manage_dialog'):
            self.music_manage_dialog.setWindowTitle(self.tr("歌曲管理"))
            self.music_manage_introduce_label.setText(self.tr("选择源文件夹和目标文件夹，将音乐文件移动到目标位置:"))
            self.source_label.setText(self.tr("源文件夹:"))
            self.dest_label.setText(self.tr("目标文件夹:"))
            self.source_browse_btn.setText(self.tr("浏览..."))
            self.dest_browse_btn.setText(self.tr("浏览..."))
            self.music_move_btn.setText(self.tr("移动文件"))

        #关闭提示信息
        if hasattr(self, 'showCloseDialog'):
            self.close_dialog_title = self.tr("提示 !!!")
            self.close_dialog_msg = self.tr("关闭宜播放器？")

        # 反馈信息
        if hasattr(self, 'feedback_dialog'):
            self.feedback_dialog.setWindowTitle(self.tr("反馈建议"))
            self.feedback_label.setText(self.tr("请填写您的反馈意见，我们将尽快处理:"))
            self.feedback_text.setPlaceholderText(self.tr("请输入您的反馈内容..."))
            self.user_email.setPlaceholderText(self.tr("您的邮箱(可选)"))
            self.feedback_send_btn.setText(self.tr("发送反馈"))
            self.feedback_cancel_btn.setText(self.tr("取消"))

        #关于页面
        self.about_title.setText(self.tr("宜播放器"))
        self.version_label.setText(self.tr("版本: {}").format(software_version))
        self.date_label.setText(self.tr("发布日期: {}").format(software_date))
        self.developer_label.setText(self.tr("开发者: {}").format(software_developer))
        self.about_page_back_button.setText(self.tr("返回主界面"))
        
        # 其他需要翻译的文本... 
        if hasattr(self, 'song_name_label'):
            if self.player.playbackState() == QMediaPlayer.StoppedState:
                self.song_name_label.setText(self.tr("未播放"))
                
        #设置音量图标
        self.volume_slider.setToolTip(self.tr("音量: {}").format(f"{self.volume}%"))

        #设置静音图标
        if hasattr(self, 'toggle_mute'):
            if self.is_muted:
                self.volume_button.setIcon(qtawesome.icon('fa5s.volume-mute', color=self.get_theme_color()))
                self.volume_button.setToolTip(self.tr("取消静音"))
            else:
                self.volume_button.setIcon(qtawesome.icon('fa5s.volume-up', color=self.get_theme_color()))
                self.volume_button.setToolTip(self.tr("静音"))
            
    def show_theme_selector(self):
        """显示主题选择界面"""
        self.left_widget.hide()
        self.right_widget.hide()
        self.theme_widget.show()

    def apply_theme(self, theme_color):
        """应用选择的主题颜色"""
        # 定义颜色变量
        if theme_color == 'pink':
            color = '#F76677'
        elif theme_color == 'blue':
            color = "#6D8CEB"
        elif theme_color == 'green':
            color = '#6DDF6D'
        elif theme_color == 'orange':
            color = '#FFA500'
        elif theme_color == 'purple':
            color = '#9B59B6'
        else:
            color = '#F76677'  # 默认粉色
        
        # 更新播放控制按钮颜色
        self.console_button_1.setIcon(qtawesome.icon('fa5s.backward', color=color))
        self.console_button_2.setIcon(qtawesome.icon('fa5s.forward', color=color))
        self.console_button_3.setIcon(qtawesome.icon('fa5s.play', color=color, font=18))
        self.console_button_3.setIcon(qtawesome.icon('fa5s.pause', color=color, font=18))
        self.console_button_mode.setIcon(qtawesome.icon('fa5s.list-ol', color=color))
        self.volume_button.setIcon(qtawesome.icon('fa5s.volume-up', color=color))

        # 更新默认专辑图标颜色
        self.album_default_icon = qtawesome.icon('fa5s.compact-disc', color=color)
        
        # 如果没有正在播放的专辑封面，更新显示
        if not hasattr(self, 'current_cover_image') or not self.current_cover_image:
            pixmap = self.album_default_icon.pixmap(60, 60)
            self.album_art_label.setPixmap(pixmap)

        
        # 更新音量滑块样式
        self.volume_slider.setStyleSheet(f"""
            QSlider::handle:horizontal {{
                background: {color};
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -8px 0;
            }}
        """)
        
        # 更新进度条样式
        self.time_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 3px;
                background: lightgray;
            }}
            QSlider::handle:horizontal {{
                width: 8px;
                height: 8px;
                background: {color};
                margin: -2px 0;
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {color};
            }}
        """)
        
        # 更新歌词和歌曲名称颜色
        self.song_name_label.setStyleSheet(f"""
            font-size: 12px; 
            color: {color};
            qproperty-alignment: AlignCenter;
        """)
        self.lyrics_label.setStyleSheet(f"""
            font-size: 12px; 
            color: {color};
            qproperty-alignment: AlignCenter;
        """)
        # 存储当前主题
        self.current_theme = theme_color

        #更新当前歌曲名显示主题颜色
        self.song_buttons[self.current_index].setStyleSheet(f'''
            QPushButton{{
                border:none;
                color:{self.get_theme_color()};
                font-size:12px;
                font-weight:bold;
                text-align:left;
            }}
            QPushButton:hover{{
                color:{self.get_theme_color()};
                border:1px solid #F3F3F5;
                border-radius:10px;
                background:LightGray;
            }}
        ''')
        #左侧模块
        self.left_widget.setStyleSheet(f'''
            QPushButton{{border:none;color:white;}}
            QPushButton#left_label{{
            border:none;
            border-bottom:1px solid white;
            font-size:18px;
            font-weight:700;
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
            }}
            QPushButton#left_button:hover{{border-left:4px solid {color};font-weight:700;}}
            ''')
        #推荐模块
        self.right_recommend_widget.setStyleSheet(f'''
            QToolButton{{border:none;}}
            QToolButton:hover{{border-bottom:2px solid {color};}}
            ''')

        #设置ToolTip显示风格
        self.set_tool_tip_style()
        
        # 更新关闭按钮颜色
        self.left_close.setIcon(qtawesome.icon('fa5s.times', color=color, font=18))
        self.left_mini.setIcon(qtawesome.icon('fa5s.window-minimize', color=color, font=18)) # 最小化按钮
        self.left_visit.setIcon(qtawesome.icon('fa5s.circle', color=color, font=18))

         # 更新收藏按钮颜色
        if hasattr(self, 'favorite_buttons'):
            target_playlist = self.filtered_playlist if hasattr(self, 'filtered_playlist') and self.filtered_playlist else self.playlist
            for i, btn in enumerate(self.favorite_buttons):
                try:
                    # 检查按钮是否仍然有效
                    if btn is None or not isinstance(btn, QPushButton):
                        continue
                        
                    if i < len(target_playlist):  # 确保索引有效
                        song_path = target_playlist[i]
                        if song_path in self.favorites:
                            btn.setIcon(qtawesome.icon('fa5s.heart', color=self.get_theme_color()))
                            btn.setIconSize(QSize(16, 16))
                            btn.setToolTip("取消收藏")
                        else:
                            btn.setIcon(qtawesome.icon('fa5s.heart', color='gray'))
                            btn.setIconSize(QSize(16, 16))
                            btn.setToolTip("添加到收藏")
                except RuntimeError:
                    # 如果按钮已被删除，跳过
                    continue

        #跟新主题页面颜色
        self.theme_title_color.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        self.theme_title_language.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        self.chinese_theme_btn.setStyleSheet(f"""
                                          QPushButton {{
                                          background:white; 
                                          color: {color};
                                          }}
                                          QPushButton:hover {{
                                          background: {color}; 
                                          color: white;
                                          }}
                                          """)
        self.english_theme_btn.setStyleSheet(f"""
                                          QPushButton {{
                                          background:white; 
                                          color: {color};
                                          }}
                                          QPushButton:hover {{
                                          background: {color}; 
                                          color: white;
                                          }}
                                          """)
        self.theme_page_back_button.setIcon(qtawesome.icon('fa5s.arrow-left', color=color))
        self.theme_page_back_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 14px;
                color: {color};
                border: 1px solid {color};
                border-radius: 5px;
                padding: 5px 10px;
                margin-top: 20px;
            }}
            QPushButton:hover {{
                background: {color};
                color: white;
            }}
        """)

        #更新about界面颜色
        self.about_title.setStyleSheet(f"font-size: 24px; font-weight: bold;color: {color};")
        self.about_page_back_button.setIcon(qtawesome.icon('fa5s.arrow-left',color=color))
        self.about_page_back_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 14px;
                color: {color};
                border: 1px solid {color};
                border-radius: 5px;
                padding: 5px 10px;
                margin-top: 20px;
            }}
            QPushButton:hover {{
                background: {color};
                color: white;
            }}
        """)

        
        # 返回主界面
        self.show_main_interface()
        # self.init_about_ui()
        # self.init_theme_ui()

    def get_theme_color(self):
        """获取当前主题颜色"""
        if self.current_theme == 'pink':
            return '#F76677'
        elif self.current_theme == 'blue':
            return "#6D8CEB"
        elif self.current_theme == 'green':
            return '#6DDF6D'
        elif self.current_theme == 'orange':
            return '#FFA500'
        elif self.current_theme == 'purple':
            return '#9B59B6'
        else:
            return '#F76677'  # 默认粉色

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.drag_position:
            # 计算窗口需要移动的距离
            delta = event.globalPosition().toPoint() - self.drag_position
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.drag_position = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.drag_position = None
            event.accept()

    def showCloseDialog(self):
        #方式一
        # reply = QMessageBox.question(self,
        #                         '提示 !!!',
        #                         '关闭宜播放器？',
        #                         QMessageBox.Yes | QMessageBox.No,
        #                         QMessageBox.No)
        # # 修改按钮文本
        # msg_box = self.findChild(QMessageBox)
        # if msg_box:
        #     yes_button = msg_box.button(QMessageBox.Yes)
        #     no_button = msg_box.button(QMessageBox.No)
        #     yes_button.setText("是")
        #     no_button.setText("否")
        # if reply == QMessageBox.Yes:
        #     sys.exit(0)
        # 方式二
        # msg_box = QMessageBox(self)
        # msg_box.setWindowTitle('提示 !!!')
        # msg_box.setText('关闭宜播放器？')
        # yes_button = msg_box.addButton("是", QMessageBox.YesRole)
        # no_button = msg_box.addButton("否", QMessageBox.NoRole)
        # msg_box.setDefaultButton(no_button)
        # msg_box.exec_()
        # if msg_box.clickedButton() == yes_button:
        #     sys.exit(0)
        #方式三
        self.close_dialog_title = self.tr("提示 !!!")
        self.close_dialog_msg = self.tr("关闭宜播放器？")
        if self.show_yes_no_dialog(self, self.close_dialog_title, self.close_dialog_msg):
            sys.exit(0)

    def show_yes_no_dialog(self, parent, title, message, yes_text= "是", no_text= "否"):
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        yes_button = msg_box.addButton(yes_text, QMessageBox.YesRole)
        no_button = msg_box.addButton(no_text, QMessageBox.NoRole)
        msg_box.setDefaultButton(no_button)
        msg_box.exec_()
        return msg_box.clickedButton() == yes_button
    
    def search_music(self):
        """搜索音乐并更新列表"""
        keyword = self.right_bar_widget_search_input.text().strip().lower()
        if not keyword:
            # 如果关键词为空，显示所有歌曲
            self.filtered_playlist = self.playlist.copy() 
            self.update_song_list(self.playlist)
            return
        
        # 过滤匹配的歌曲
        self.filtered_playlist = []  # 存储过滤后的列表
        for song in self.playlist:
            filename = os.path.basename(song).lower()
            if keyword in filename:
                self.filtered_playlist.append(song)  
        
        # 更新歌曲列表显示
        self.update_song_list(self.filtered_playlist)  

    def update_song_list(self, songs):
        """更新歌曲列表显示"""
        # 清除现有行
        for i in reversed(range(self.song_scroll_layout.count())): 
            # self.song_scroll_layout.itemAt(i).widget().setParent(None)
            widget = self.song_scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.song_buttons = []
        self.song_duration_labels = []
        self.favorite_buttons = []  # 新增：清空收藏按钮列表
        self.song_durations = [0] * len(songs)  # 重置时长列表
        
        # 为每首歌创建一行
        for i in range(len(songs)):
            container = self._create_song_row(i)
            if container is None:
                continue
                
            # 获取音乐文件时长
            audio_time = self.get_audio_duration(songs[i])
            filename = os.path.basename(songs[i])
            self.song_buttons[i].setText(filename)
            self.song_duration_labels[i].setText(audio_time)
            
            # 更新收藏按钮状态
            if songs[i] in self.favorites:
                self.favorite_buttons[i].setIcon(qtawesome.icon('fa5s.heart', color=self.get_theme_color()))
                self.favorite_buttons[i].setIconSize(QSize(16, 16))
                self.favorite_buttons[i].setToolTip("取消收藏")
            else:
                self.favorite_buttons[i].setIcon(qtawesome.icon('fa5s.heart', color='gray'))
                self.favorite_buttons[i].setIconSize(QSize(16, 16))
                self.favorite_buttons[i].setToolTip("添加到收藏")

    def _create_song_row(self, index):
        """创建一行歌曲显示元素"""
        if not hasattr(self, 'favorite_buttons'):
            self.favorite_buttons = []
        # 检查索引是否有效
        target_playlist = self.filtered_playlist if hasattr(self, 'filtered_playlist') and self.filtered_playlist else self.playlist
        if index >= len(target_playlist):
            return None
        
        container = QWidget()
        container.setFixedHeight(40)  # 固定高度
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)  # 添加间距
        layout.setAlignment(Qt.AlignVCenter)  # 垂直居中
        
        # 收藏按钮 - 增加边距和固定宽度
        favorite_btn = QPushButton("")
        favorite_btn.setFixedSize(24, 24)  # 增大按钮尺寸
        favorite_btn.setProperty('index', index)
        favorite_btn.clicked.connect(self.toggle_favorite_status)
        
        # 初始设置图标- 使用当前主题颜色
        song_path = target_playlist[index]
        if song_path in self.favorites:
            favorite_btn.setIcon(qtawesome.icon('fa5s.heart', color=self.get_theme_color()))
        else:
            favorite_btn.setIcon(qtawesome.icon('fa5s.heart', color='gray'))
        favorite_btn.setIconSize(QSize(16, 16))
        favorite_btn.setStyleSheet('''
            QPushButton {
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
        ''')
        
        # 歌曲按钮 - 设置最小宽度和弹性空间
        btn = QPushButton("")
        btn.setProperty('index', index)
        btn.clicked.connect(self.play_selected_song)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # 水平扩展
        btn.setStyleSheet('''
            QPushButton{
                border:none;
                color:gray;
                font-size:12px;
                text-align:left;
                padding-left: 5px;
            }
            QPushButton:hover{
                color:black;
                border:1px solid #F3F3F5;
                border-radius:10px;
                background:LightGray;
            }
        ''')
        
        # 时长标签 - 固定宽度
        duration_label = QLabel("")
        duration_label.setFixedWidth(50)  # 固定宽度防止挤压
        duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        duration_label.setStyleSheet('''
            QLabel {
                font-size: 10px;
                color: gray;
                padding-right: 5px;
            }
        ''')
        
        layout.addWidget(favorite_btn)
        layout.addWidget(btn)
        layout.addWidget(duration_label)
        
        self.song_scroll_layout.addWidget(container)
        self.song_buttons.append(btn)
        self.song_duration_labels.append(duration_label)
        if not hasattr(self, 'favorite_buttons'):
            self.favorite_buttons = []
        # 确保只添加有效按钮
        if favorite_btn:
            self.favorite_buttons.append(favorite_btn)
        return container

    def format_time(self, milliseconds):
        """将毫秒转换为 mm:ss 格式"""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_audio_duration(self, file_path):
        # 根据文件扩展名选择适当的解析器
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.mp3':
                audio = MP3(file_path)
            elif ext == '.flac':
                audio = FLAC(file_path)
            elif ext == '.wav':
                audio = WAVE(file_path)
            else:
                return None  # 不支持的文件格式
            #转化为毫秒
            res = self.format_time(int(audio.info.length) * 1000)
            return res  # 返回时长（秒）
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None
        
    def auto_load_music(self):
        """自动加载music文件夹下的音乐文件"""
        music_dir = os.path.join(os.getcwd(), 'music')
        # 如果music文件夹不存在，则创建
        if not os.path.exists(music_dir):
            os.makedirs(music_dir)
            return
        
        # 获取所有支持的音频文件
        supported_formats = ('.mp3', '.wav', '.ogg', '.flac')
        music_files = []
        for file in os.listdir(music_dir):
            if file.lower().endswith(supported_formats):
                music_files.append(os.path.join(music_dir, file))
        
        # 如果有音乐文件，则加载
        if music_files:
            self.playlist = music_files
            self.filtered_playlist = music_files.copy()
            self.current_index = -1
            self.song_durations = [0] * len(music_files)
            
            # 清除现有行
            for i in reversed(range(self.song_scroll_layout.count())): 
                self.song_scroll_layout.itemAt(i).widget().setParent(None)
            self.song_buttons = []
            self.song_duration_labels = []
            
            self.load_favorites()
            # for i in self.favorites:
            #     print(f'favorites items: {i}')
            # 为每首歌创建一行
            for i in range(len(music_files)):
                self._create_song_row(i)
                
                # 获取音乐文件时长
                audio_time = self.get_audio_duration(music_files[i])
                filename = os.path.basename(music_files[i])
                self.song_buttons[i].setText(f'{filename}  {audio_time}')
        
    def load_local_music(self):
        """加载本地音乐文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音乐文件", "", "音频文件 (*.mp3 *.wav *.ogg *.flac);;所有文件 (*)"
        )
        
        if files:
            self.playlist = files
            self.filtered_playlist = files.copy()
            self.current_index = -1
            self.song_durations = [0] * len(files)  # 初始化时长列表
            
            # 清除现有行
            for i in reversed(range(self.song_scroll_layout.count())): 
                self.song_scroll_layout.itemAt(i).widget().setParent(None)
            self.song_buttons = []
            self.song_duration_labels = []

            self.load_favorites()
            # 为每首歌创建一行
            for i in range(len(files)):
                self._create_song_row(i)
                
                # 获取音乐文件时长
                audio_time = self.get_audio_duration(files[i])
                filename = os.path.basename(files[i])
                self.song_buttons[i].setText(f'{filename}  {audio_time}')
                #self.song_duration_labels[i].setText(audio_time)

    def show_music_manager(self):
        """显示音乐管理对话框"""
        self.music_manage_dialog = QDialog(self)
        self.music_manage_dialog.setWindowTitle(self.tr("歌曲管理"))
        self.music_manage_dialog.setFixedSize(550, 180)
        
        self.music_manage_layout = QVBoxLayout(self.music_manage_dialog)
        
        # 添加说明标签
        self.music_manage_introduce_label = QLabel(self.tr("选择源文件夹和目标文件夹，将音乐文件移动到目标位置:"))
        self.music_manage_layout.addWidget(self.music_manage_introduce_label)
        
        # 源文件夹选择
        self.source_layout = QHBoxLayout()
        self.source_label = QLabel(self.tr("源文件夹:"))
        self.source_path_edit = QLineEdit()
        self.source_path_edit.setReadOnly(True)
        self.source_browse_btn = QPushButton(self.tr("浏览..."))
        self.source_browse_btn.clicked.connect(lambda: self.browse_folder(self.source_path_edit))
        self.source_layout.addWidget(self.source_label)
        self.source_layout.addWidget(self.source_path_edit)
        self.source_layout.addWidget(self.source_browse_btn)
        self.music_manage_layout.addLayout(self.source_layout)
        
        # 目标文件夹选择
        self.dest_layout = QHBoxLayout()
        self.dest_label = QLabel(self.tr("目标文件夹:"))
        self.dest_path_edit = QLineEdit()
        self.dest_path_edit.setReadOnly(True)
        self.dest_browse_btn = QPushButton(self.tr("浏览..."))
        self.dest_browse_btn.clicked.connect(lambda: self.browse_folder(self.dest_path_edit))
        self.dest_layout.addWidget(self.dest_label)
        self.dest_layout.addWidget(self.dest_path_edit)
        self.dest_layout.addWidget(self.dest_browse_btn)
        self.music_manage_layout.addLayout(self.dest_layout)
        
        # 文件类型选择
        self.mp3_check = QCheckBox("MP3 (.mp3)")
        self.mp3_check.setChecked(True)
        self.wav_check = QCheckBox("WAV (.wav)")
        self.wav_check.setChecked(True)
        self.flac_check = QCheckBox("FLAC (.flac)")
        self.flac_check.setChecked(True)
        self.ogg_check = QCheckBox("OGG (.ogg)")
        self.ogg_check.setChecked(True)
        self.lrc_check = QCheckBox("LRC (.lrc)")
        self.lrc_check.setChecked(True)
        
        self.filetype_layout = QHBoxLayout()
        self.filetype_layout.addWidget(QLabel(self.tr("文件类型:")))
        self.filetype_layout.addWidget(self.mp3_check)
        self.filetype_layout.addWidget(self.wav_check)
        self.filetype_layout.addWidget(self.flac_check)
        self.filetype_layout.addWidget(self.ogg_check)
        self.filetype_layout.addWidget(self.lrc_check)
        self.filetype_layout.addStretch()
        self.music_manage_layout.addLayout(self.filetype_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        # 移动按钮
        self.music_move_btn = QPushButton(self.tr("移动文件"))
        self.music_move_btn.clicked.connect(lambda: self.move_music_files(self.music_manage_dialog))
        self.music_move_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.get_theme_color()};
                color: white;
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                background: white;
                color: {self.get_theme_color()};
                border: 1px solid {self.get_theme_color()};
            }}
        """)
        
        # 取消按钮
        self.music_cancel_btn = QPushButton(self.tr("取消"))
        self.music_cancel_btn.clicked.connect(self.music_manage_dialog.reject)
        self.music_cancel_btn.setStyleSheet("""
            QPushButton {
                background: #ccc;
                color: black;
                border-radius: 5px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background: #aaa;
            }
        """)
        
        button_layout.addWidget(self.music_move_btn)
        button_layout.addWidget(self.music_cancel_btn)
        self.music_manage_layout.addLayout(button_layout)
        
        self.music_manage_dialog.exec_()

    def browse_folder(self, line_edit):
        """浏览文件夹并设置路径到指定的QLineEdit"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            line_edit.setText(folder)

    def move_music_files(self, dialog):
        """移动音乐文件"""
        source_folder = self.source_path_edit.text()
        dest_folder = self.dest_path_edit.text()
        
        if not source_folder or not dest_folder:
            QMessageBox.warning(self, "警告", "请选择源文件夹和目标文件夹")
            return
        
        if source_folder == dest_folder:
            QMessageBox.warning(self, "警告", "源文件夹和目标文件夹不能相同")
            return
        
        # 获取选中的文件类型
        file_types = []
        if self.mp3_check.isChecked():
            file_types.append('.mp3')
        if self.wav_check.isChecked():
            file_types.append('.wav')
        if self.flac_check.isChecked():
            file_types.append('.flac')
        if self.ogg_check.isChecked():
            file_types.append('.ogg')
        if self.ogg_check.isChecked():
            file_types.append('.lrc')
        
        if not file_types:
            QMessageBox.warning(self, "警告", "请至少选择一种文件类型")
            return
        
        # 创建进度对话框
        progress = QProgressDialog("正在移动文件...", "取消", 0, 100, self)
        progress.setWindowTitle("请稍候")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        
        try:
            # 获取所有匹配的文件
            all_files = []
            for root, _, files in os.walk(source_folder):
                for file in files:
                    if os.path.splitext(file)[1].lower() in file_types:
                        all_files.append(os.path.join(root, file))
            
            if not all_files:
                QMessageBox.information(self, "提示", "没有找到符合条件的音乐文件")
                return
            
            total_files = len(all_files)
            moved_files = 0
            
            # 确保目标文件夹存在
            os.makedirs(dest_folder, exist_ok=True)
            
            for i, file_path in enumerate(all_files):
                if progress.wasCanceled():
                    break
                    
                # 更新进度
                progress.setValue(int((i + 1) / total_files * 100))
                QApplication.processEvents()  # 保持UI响应
                
                try:
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(dest_folder, file_name)
                    
                    # 处理重名文件
                    counter = 1
                    while os.path.exists(dest_path):
                        name, ext = os.path.splitext(file_name)
                        dest_path = os.path.join(dest_folder, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    # 移动文件
                    shutil.move(file_path, dest_path)
                    moved_files += 1
                except Exception as e:
                    print(f"移动文件 {file_path} 失败: {e}")
            
            # 完成后的提示
            progress.close()
            if moved_files > 0:
                QMessageBox.information(self, "完成", f"成功移动 {moved_files}/{total_files} 个文件")
                
                # 如果移动到了music文件夹，自动刷新列表
                if os.path.abspath(dest_folder) == os.path.abspath(music_path):
                    self.auto_load_music()
            else:
                QMessageBox.warning(self, "提示", "没有移动任何文件")
        
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "错误", f"移动文件时出错: {str(e)}")
        
        dialog.accept()

    def load_lyrics(self, song_path):
        """加载歌词文件"""
        self.lyrics = []
        self.current_lyric_index = 0
        
        # 获取歌词文件路径（与歌曲同名，扩展名为.lrc）
        base_path = os.path.splitext(song_path)[0]
        lrc_path = base_path + '.lrc'
        
        if not os.path.exists(lrc_path):
            self.song_name_label.setText(os.path.basename(song_path))
            self.lyrics_label.setText("未找到歌词文件")
            return
        
        try:
            with open(lrc_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                for line in lines:
                    line = line.strip()
                    if not line or ']' not in line:
                        continue
                    
                    # 处理时间标签
                    parts = line.split(']')
                    time_str = parts[0][1:]  # 去掉开头的'['
                    
                    try:
                        # 解析时间格式 [mm:ss.xx]
                        time_parts = time_str.split(':')
                        if len(time_parts) == 2:
                            minutes = float(time_parts[0])
                            seconds = float(time_parts[1])
                            total_ms = int((minutes * 60 + seconds) * 1000)
                            
                            # 添加歌词
                            lyric_text = ']'.join(parts[1:]).strip()
                            if lyric_text:
                                self.lyrics.append((total_ms, lyric_text))
                    except ValueError:
                        continue
                
                # 按时间排序歌词
                self.lyrics.sort(key=lambda x: x[0])
                
                # 更新歌曲名称
                self.song_name_label.setText(f'{os.path.basename(song_path)}')
                
                # 如果没有歌词，显示提示
                if not self.lyrics:
                    self.lyrics_label.setText("无歌词内容")
                else:
                    # 显示第一句歌词和下一句歌词（如果有）
                    current_lyric = self.lyrics[0][1]
                    next_lyric = self.lyrics[1][1] if len(self.lyrics) > 1 else ""
                    self.lyrics_label.setText(f"{current_lyric}\n{next_lyric}")
        
        except Exception as e:
            print(f"加载歌词失败: {e}")
            self.song_name_label.setText(os.path.basename(song_path))
            self.lyrics_label.setText("歌词加载错误")

    def update_lyrics(self, position):
        """根据播放位置更新显示的歌词（14行）"""
        if not self.lyrics:
            return
            
        # 找到当前应该显示的歌词
        new_index = 0
        for i, (time_ms, _) in enumerate(self.lyrics):
            if position >= time_ms:
                new_index = i
            else:
                break
                
        # 如果歌词索引变化，更新显示
        if new_index != self.current_lyric_index:
            self.current_lyric_index = new_index
            
            # 获取前后共15行歌词（当前行前后各5行）
            start_index = max(0, self.current_lyric_index - 6)
            end_index = min(len(self.lyrics), self.current_lyric_index + 9)  # 包括当前行
            display_lyrics = self.lyrics[start_index:end_index]

            lyrics_html = ""
            for i, (time_ms, lyric_text) in enumerate(display_lyrics):
                idx = start_index + i
                if idx == self.current_lyric_index:
                    # 当前行高亮显示
                    lyrics_html += f"<div style='font-size:14px; color:{self.get_theme_color()}; font-weight:bold; margin:5px 0;'>▶ {lyric_text}</div>"
                else:
                    # 其他行普通显示
                    lyrics_html += f"<div style='font-size:12px; color:#888;'>{lyric_text}</div>"

            # 如果歌词不足14行，补充空行保持高度一致
            for _ in range(14 - len(display_lyrics)):
                lyrics_html += "<div style='font-size:12px; color:#888;'>&nbsp;</div>"
                
            self.lyrics_label.setText(lyrics_html)

    def toggle_play_mode(self):
        """切换播放模式"""
        self.play_mode = (self.play_mode + 1) % 4
        if self.play_mode == 0:
            self.console_button_mode.setIcon(qtawesome.icon('fa5s.list-ol', color=self.get_theme_color()))
            self.console_button_mode.setToolTip(self.tr("顺序播放"))
        elif self.play_mode == 1:
            self.console_button_mode.setIcon(qtawesome.icon('fa5s.infinity', color=self.get_theme_color()))
            self.console_button_mode.setToolTip(self.tr("循环播放"))
        elif self.play_mode == 2:
            self.console_button_mode.setIcon(qtawesome.icon('fa5s.redo', color=self.get_theme_color()))
            self.console_button_mode.setToolTip(self.tr("单曲循环"))
        else:
            self.console_button_mode.setIcon(qtawesome.icon('fa5s.random', color=self.get_theme_color()))
            self.console_button_mode.setToolTip(self.tr("随机播放"))

    def toggle_mute(self):
        """切换静音状态"""
        self.is_muted = not self.is_muted
        self.audio_output.setMuted(self.is_muted)
        
        # 更新按钮图标
        if self.is_muted:
            self.volume_button.setIcon(qtawesome.icon('fa5s.volume-mute', color=self.get_theme_color()))
            self.volume_button.setToolTip(self.tr("取消静音"))
        else:
            self.volume_button.setIcon(qtawesome.icon('fa5s.volume-up', color=self.get_theme_color()))
            self.volume_button.setToolTip(self.tr("静音"))

    def set_volume(self, value):
        """设置音量"""
        self.volume = value
        self.audio_output.setVolume(value / 100)
        
        # 根据音量大小更新图标
        if value == 0:
            self.volume_button.setIcon(qtawesome.icon('fa5s.volume-mute', color=self.get_theme_color()))
        elif value < 50:
            self.volume_button.setIcon(qtawesome.icon('fa5s.volume-down', color=self.get_theme_color()))
        else:
            self.volume_button.setIcon(qtawesome.icon('fa5s.volume-up', color=self.get_theme_color()))
        
        # 如果从静音状态调整音量，自动取消静音
        if self.is_muted and value > 0:
            self.is_muted = False
            self.audio_output.setMuted(False)
            self.volume_button.setToolTip(self.tr("静音"))
        
    def play_selected_song(self):
        """播放选中的歌曲"""
        sender = self.sender()
        index = sender.property('index')
        # if 0 <= index < len(self.filtered_playlist):  
        #     # 找到在原始播放列表中的索引
        #     song_path = self.filtered_playlist[index] 
        #     self.current_index = self.playlist.index(song_path) 
        #     self.play_current_song()
        # 确保使用正确的播放列表
        target_playlist = self.filtered_playlist if hasattr(self, 'filtered_playlist') and self.filtered_playlist else self.playlist
        
        if 0 <= index < len(target_playlist):
            song_path = target_playlist[index]
            try:
                self.current_index = self.playlist.index(song_path)
                self.play_current_song()
            except ValueError:
                # 如果歌曲不在原始播放列表中，直接播放
                self.current_index = index
                self.play_current_song()
    
    def play_current_song(self):
        """播放当前索引的歌曲"""
        if 0 <= self.current_index < len(self.playlist):
            # 重置所有按钮的样式
            for btn in self.song_buttons:
                btn.setStyleSheet('''
                    QPushButton{
                        border:none;
                        color:gray;
                        font-size:12px;
                        text-align:left;
                    }
                    QPushButton:hover{
                        color:black;
                        border:1px solid #F3F3F5;
                        border-radius:10px;
                        background:LightGray;
                    }
                ''')

            # 尝试加载专辑封面
            song_path = self.playlist[self.current_index]
            self.update_album_art(song_path)
            
            # 根据目前主题设置当前播放按钮的样式颜色
            if 0 <= self.current_index < len(self.song_buttons):
                self.song_buttons[self.current_index].setStyleSheet(f'''
                    QPushButton{{
                        border:none;
                        color:{self.get_theme_color()};
                        font-size:12px;
                        font-weight:bold;
                        text-align:left;
                    }}
                    QPushButton:hover{{
                        color:{self.get_theme_color()};
                        border:1px solid #F3F3F5;
                        border-radius:10px;
                        background:LightGray;
                    }}
                ''')
            
            media = QUrl.fromLocalFile(self.playlist[self.current_index])
            self.player.setSource(media)
            self.player.play()
            self.console_button_3.setIcon(qtawesome.icon('fa5s.pause', color=self.get_theme_color(), font=18))
            
            # 确保音量设置正确
            self.audio_output.setVolume(self.volume / 100)
            self.audio_output.setMuted(self.is_muted)
            
            # 更新歌曲名称
            song_name = os.path.basename(self.playlist[self.current_index])
            self.song_name_label.setText(song_name)
            self.lyrics_label.setText(self.tr("加载中..."))
            
            # 加载歌词
            self.load_lyrics(self.playlist[self.current_index])

    def update_album_art(self, song_path):
        """更新专辑封面显示"""
        # 尝试从音乐文件获取封面
        self.cover_image = self.extract_cover_image(song_path)
        
        if self.cover_image:
            # 缩放图片以适应标签大小
            pixmap = QPixmap.fromImage(self.cover_image)
            pixmap = pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.album_art_label.setPixmap(pixmap)
        else:
            # 使用默认音乐图标
            self.album_default_icon = qtawesome.icon('fa5s.compact-disc', color=self.get_theme_color())
            pixmap = self.album_default_icon.pixmap(60, 60)
            self.album_art_label.setPixmap(pixmap)

    def extract_cover_image(self, file_path):
        """从音乐文件中提取封面图片"""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.mp3':
                audio = MP3(file_path)
                if 'APIC:' in audio.tags:
                    cover = audio.tags['APIC:'].data
                    image = QImage.fromData(cover)
                    return image
            elif ext == '.flac':
                audio = FLAC(file_path)
                if audio.pictures:
                    image = QImage.fromData(audio.pictures[0].data)
                    return image
            
            # 检查同一目录下是否有封面图片
            folder = os.path.dirname(file_path)
            for f in os.listdir(folder):
                if f.lower() in ('cover.jpg', 'folder.jpg', 'album.jpg', 'front.jpg'):
                    image = QImage(os.path.join(folder, f))
                    return image
                    
        except Exception as e:
            print(f"无法提取封面图片: {e}")
        
        return None

    def handle_media_status(self, status):
        """处理媒体状态变化"""
        if status == QMediaPlayer.EndOfMedia:
            # 歌曲播放完毕，根据播放模式决定下一首
            if self.play_mode == 2:  # 单曲循环
                self.player.setPosition(0)
                self.player.play()
            else:  # 其他模式播放下一首
                self.play_next()
    
    def toggle_play_pause(self):
        """切换播放/暂停状态"""
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.console_button_3.setIcon(qtawesome.icon('fa5s.play', color=self.get_theme_color(), font=18))
        else:
            if self.player.source().isEmpty() and self.playlist:
                # 如果没有加载任何歌曲但有播放列表，播放第一首
                self.current_index = 0
                self.play_current_song()
            else:
                self.player.play()
                self.console_button_3.setIcon(qtawesome.icon('fa5s.pause', color=self.get_theme_color(), font=18))
    
    def play_next(self):
        """播放下一首"""
        if not self.playlist:
            return
            
        if self.play_mode == 3:  # 随机播放
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            self.current_index += 1
            if self.current_index >= len(self.playlist):
                if self.play_mode == 1:  # 循环播放
                    self.current_index = 0
                else:  # 顺序播放
                    self.current_index = -1
                    return
        
        self.play_current_song()
    
    def play_previous(self):
        """播放上一首"""
        if not self.playlist:
            return
            
        if self.play_mode == 3:  # 随机播放
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            self.current_index -= 1
            if self.current_index < 0:
                if self.play_mode == 1:  # 循环播放
                    self.current_index = len(self.playlist) - 1
                else:  # 顺序播放
                    self.current_index = -1
                    return
        
        self.play_current_song()
    
    def update_position(self, position):
        """更新播放位置"""
        if hasattr(self, 'is_slider_pressed') and self.is_slider_pressed:
            return  # 如果滑块正在被拖动，不自动更新位置
        if self.player.duration() > 0:
            progress = int((position / self.player.duration()) * 100)
            # self.right_process_bar.setValue(progress)
            self.time_slider.setValue(progress)
            self.current_time_label.setText(self.format_time(position))

            # 更新歌词显示
            self.update_lyrics(position)
    
    def update_duration(self, duration):
        """更新歌曲总时长"""
        if duration > 0:
            self.total_time_label.setText(self.format_time(duration))
            
            # 更新当前歌曲的时长显示
            # if 0 <= self.current_index < len(self.playlist):
            #     self.song_durations[self.current_index] = duration
            #     self.song_duration_labels[self.current_index].setText(self.format_time(duration))
            if 0 <= self.current_index < len(self.playlist):
            # 如果列表长度不足，先扩展
                while len(self.song_durations) <= self.current_index:
                    self.song_durations.append(0)
                
                self.song_durations[self.current_index] = duration
                if self.current_index < len(self.song_duration_labels):
                    self.song_duration_labels[self.current_index].setText(self.format_time(duration))
    
    def seek_position(self, position):
        """跳转到指定位置"""
        if self.player.duration() > 0:
            seek_pos = int((position / 100) * self.player.duration())
            self.player.setPosition(seek_pos)
    
    def update_buttons(self, state):
        """根据播放状态更新按钮"""
        if state == QMediaPlayer.PlayingState:
            self.console_button_3.setIcon(qtawesome.icon('fa5s.pause', color=self.get_theme_color(), font=18))
        else:
            self.console_button_3.setIcon(qtawesome.icon('fa5s.play', color=self.get_theme_color(), font=18))
    
    def update_progress(self):
        """定时更新进度条"""
        if self.player.duration() > 0 and self.player.playbackState() == QMediaPlayer.PlayingState:
            position = self.player.position()
            duration = self.player.duration()
            progress = int((position / duration) * 100)
            # self.right_process_bar.setValue(progress)
            self.time_slider.setValue(progress)
            self.current_time_label.setText(self.format_time(position))

    def eventFilter(self, source, event):
        """事件过滤器，用于处理进度条悬停提示"""
        if source == self.time_slider and event.type() == QEvent.HoverMove:
            # 计算鼠标位置对应的时间
            pos = event.pos().x()
            value = pos / self.time_slider.width() * 100
            if self.player.duration() > 0:
                time_ms = int(value / 100 * self.player.duration())
                # 显示工具提示
                QToolTip.showText(
                    event.globalPosition().toPoint(), 
                    self.format_time(time_ms),
                    self.time_slider
                )
        return super().eventFilter(source, event)

    # 添加滑块处理方法
    def slider_pressed(self):
        """滑块被按下时暂停自动更新"""
        self.timer.stop()
        self.is_slider_pressed = True  # 新增标志位

    def slider_released(self):
        """滑块释放时恢复播放和定时器"""
        self.is_slider_pressed = False  # 重置标志位
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            # 跳转到滑块位置
            position = self.time_slider.value()
            seek_pos = int((position / 100) * self.player.duration())
            self.player.setPosition(seek_pos)
            self.timer.start(1000)

    def slider_moved(self, position):
        """滑块移动时更新显示"""
        if not hasattr(self, 'is_slider_pressed') or not self.is_slider_pressed:
            return
            
        if self.player.duration() > 0:
            seek_pos = int((position / 100) * self.player.duration())
            self.current_time_label.setText(self.format_time(seek_pos))

    def slider_mouse_press_event(self, event):
        """处理鼠标点击进度条事件"""
        if event.button() == Qt.LeftButton:
            # 计算点击位置对应的值
            pos = event.pos().x()
            value = self.time_slider.minimum() + (self.time_slider.maximum() - self.time_slider.minimum()) * pos / self.time_slider.width()
            self.time_slider.setValue(int(value))
            self.slider_pressed()  # 调用按下处理
            self.slider_moved(int(value))  # 更新显示

    def slider_mouse_release_event(self, event):
        """处理鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.slider_released()  # 调用释放处理

def main():
    app = QApplication(sys.argv)
    # 设置默认语言
    # locale = QLocale.system().name()
    # print(f'locale={locale}')
    translator = QTranslator()
    if translator.load(f'yiplayer_zh.qm', 'translations'):
        print(f'translator={translator}')
        app.installTranslator(translator)
    gui = MainUi()
    gui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main() 
