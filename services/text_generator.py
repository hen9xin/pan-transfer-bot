"""
本地文案生成与二创改写器 - 无需调用任何外部 AI API
1. 支持根据原帖文案进行本地智能二创改写（句式重组、近义词替换、爆款标签、Emoji装点）
2. 支持根据网盘文件信息（名称、类型、大小、数量）自动生成二创推广文案
"""
import random
import re
from typing import Dict, List, Optional, Any

# 文件扩展名分类
FILE_CATEGORIES = {
    'video': ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'rmvb', 'ts', 'webm'],
    'audio': ['mp3', 'flac', 'wav', 'aac', 'ogg', 'wma', 'ape'],
    'document': ['pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx', 'xls', 'xlsx', 'csv', 'md'],
    'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'psd', 'ai', 'svg', 'webp', 'ico'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'],
    'code': ['py', 'js', 'html', 'css', 'java', 'cpp', 'c', 'go', 'rs', 'ts', 'vue', 'jsx', 'php', 'sql'],
    'ebook': ['epub', 'mobi', 'azw3', 'chm'],
    'software': ['exe', 'msi', 'dmg', 'apk', 'ipa', 'deb', 'rpm'],
    'subtitle': ['srt', 'ass', 'ssa', 'sub'],
}

# 分类对应 Emoji
CATEGORY_EMOJIS = {
    'video': ['🎬', '📺', '🎥', '🍿', '📽️', '🎞️', '📀'],
    'audio': ['🎵', '🎶', '🎧', '🎤', '🎼', '🔊', '💿'],
    'document': ['📄', '📝', '📑', '📋', '📊', '📈', '✏️'],
    'image': ['🖼️', '📸', '🎨', '📷', '🌄', '✨'],
    'archive': ['📦', '🗂️', '💼', '🎁', '📂'],
    'code': ['💻', '⌨️', '🖥️', '🔧', '⚙️', '🛠️', '👨‍💻'],
    'ebook': ['📚', '📖', '📕', '📗', '📘', '🔖', '📙'],
    'software': ['💾', '📲', '⚙️', '🔧', '💿', '🖥️'],
    'subtitle': ['💬', '🗨️', '📝', '🎬'],
    'general': ['🔥', '✨', '💎', '⭐', '🚀', '💯', '📌', '👀', '❤️', '🎉'],
}

# 爆款开头钩子
OPENING_HOOKS = [
    "{emoji} 宝藏干货分享！{title}",
    "{emoji} 全网精选｜{title}",
    "{emoji} {title} 完整资源打包，速存！",
    "{emoji} 亲测好用！{title} 整理好了",
    "{emoji} 收藏级资源：{title}",
    "{emoji} 刚刚整理好的 {title}，无套路自取！",
    "{emoji} 别到处找了！{title} 完整版来了",
    "{emoji} 神仙资源安利｜{title}",
    "{emoji} 吹爆这个！{title}，建议马住慢慢看",
    "{emoji} {title} 终于找到了，随时可能失效先存！",
]

# 分类特色评语
CATEGORY_TEMPLATES = {
    'video': [
        "画质原画超清，音画同步已亲测",
        "超清4K/1080P画质，视觉盛宴",
        "珍藏版画质拉满，错过拍大腿",
        "清晰度绝了，强烈推荐收藏",
    ],
    'audio': [
        "母带级无损高音质，耳朵怀孕系列",
        "高码率无损音源，发烧友必藏",
        "沉浸式纯净音质，闭眼入无雷",
    ],
    'document': [
        "干货满满无废话，职场与学习必备",
        "体系超全，小白也能快速上手",
        "条理清晰内容详尽，省去几天搜索时间",
    ],
    'image': [
        "超高清无水印原图，直接拿来当壁纸/素材",
        "分辨率拉满，精选顶级画质合集",
        "审美在线，设计与审美狂喜",
    ],
    'code': [
        "完整项目源码无删减，解压即可运行",
        "代码注释规范清晰，附带详细部署指引",
        "极简架构可本地部署，拿来即用超省心",
    ],
    'ebook': [
        "精美排版EPUB/PDF双格式，手机平板电脑完美通读",
        "无错字精校版本，深度阅读必备",
        "常读常新经典之作，值得细细品味",
    ],
    'general': [
        "纯手工整理归纳，免去繁琐到处求资源",
        "全部打包完毕，省心省力一键转存",
        "全网深度搜罗，只留最精华的部分",
        "资源难得，且存且珍惜",
    ],
}

# 结尾引导语
CLOSING_CTAS = [
    "\n\n👉 觉得有用请【点赞 + 转推】防走丢！",
    "\n\n📌 建议先转存后查阅，免得想用时找不到～",
    "\n\n⚡ 随时可能被和谐，需要的抓紧时间保存！",
    "\n\n❤️ 免费分享不易，您的点赞就是更新的动力！",
    "\n\n💬 喜欢请收藏支持，更多优质资源持续同步中～",
]

# 近义词/同义表达词典（用于本地改写变换用词）
SYNONYMS_MAP = {
    "源码": ["完整代码打包", "全套项目程序", "开源工程", "底层代码"],
    "测试": ["实测", "测评", "评测", "深度体检"],
    "本地使用": ["支持本地单机运行", "无需联网即点即开", "脱机可用零门槛"],
    "服务器部署": ["支持一键云端搭建", "可在VPS/主机快速上线", "多端自建部署"],
    "整理": ["精细归纳打包", "地毯式搜集汇编", "全网搜罗归整"],
    "分享": ["无偿放送", "免门槛自取", "倾囊相授", "开源赠送"],
    "推荐": ["按头安利", "闭眼入不踩雷", "良心力荐"],
    "免费": ["零套路赠送", "完全免费分享", "白嫖福袋"],
    "合集": ["全家桶大礼包", "全套豪华合辑", "一站式资源库"],
    "教程": ["从零到一实操手册", "通关秘籍", "避坑指引"],
    "打包": ["压缩打包封存", "一键合辑整合", "整套齐活"],
    "下载": ["保存转存", "一键收纳", "秒速下载"],
    "最新": ["刚出炉的全新版本", "当下最热门款", "抢鲜迭代版"],
    "神器": ["效率利器", "黑科技宝藏", "王炸级工具"],
}

# 句式重构替换词首
PREFIX_HOOKS = [
    "🔥 人手必备神器！",
    "💡 挖掘到一个神级资源：",
    "⚡ 告别繁琐！超实用资源直出：",
    "🚀 效率起飞！必须安利这个：",
    "💎 挖到宝了！强烈建议收藏：",
]

def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes is None or size_bytes <= 0:
        return ""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}PB"


def detect_category(files: List[Dict[str, Any]]) -> str:
    """根据文件列表检测主要文件类型分类"""
    if not files:
        return 'general'
    category_counts: Dict[str, int] = {}
    for f in files:
        name = f.get('file_name', f.get('name', ''))
        ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        for cat, extensions in FILE_CATEGORIES.items():
            if ext in extensions:
                category_counts[cat] = category_counts.get(cat, 0) + 1
                break
    if not category_counts:
        return 'general'
    return max(category_counts, key=category_counts.get)


def clean_title(title: str) -> str:
    """清洗提取纯净标题"""
    if not title:
        return "优质精选资源"
    title = re.sub(r'\.(zip|rar|7z|tar\.gz|mp4|mkv|pdf|epub|txt)$', '', title, flags=re.IGNORECASE)
    title = title.strip().strip('_').strip('-').strip('.')
    return title if title else "优质精选资源"


def rewrite_text_locally(
    raw_text: str,
    platform: str = "quark",
    share_link: str = "",
    passcode: str = ""
) -> str:
    """
    纯本地算法对原帖文案进行二次创作改写（无外部 API 依赖）
    - 清理冗余链接与提取码文本
    - 近义词语义替换与句式重组
    - 结构化分行与 Emoji 点缀
    - 增强推特/X 爆款文风与排版
    """
    text = raw_text.strip()
    if not text:
        return "🔥 精选高价值资源包整理完毕，免解压极速转存～\n💻 电脑手机多端通用，收藏防走丢！"

    # 清理已有的 url
    text = re.sub(r'https?://[^\s\u4e00-\u9fa5\r\n]+', '', text)
    # 清理“提取码：xxxx”等多余后缀标记
    # 清理“提取码：xxxx”等多余后缀标记
    text = re.sub(r'(?:提取码|密码|访问码|提取|pwd)\s*[:：]?\s*[a-zA-Z0-9]{3,6}', '', text, flags=re.IGNORECASE)
    # 清理遗留的孤立符号（如 🔗:、链接:、⬇️ 等）
    text = re.sub(r'(?:🔗|👉|👇|⬇️|链接|地址|网盘|传送门)\s*[:：]?', '', text)

    # 拆分有效短句
    raw_sentences = re.split(r'[，,。！!\n\r;；]+', text)
    valid_sentences = [
        s.strip() for s in raw_sentences
        if len(s.strip()) >= 2 and s.strip() not in ['🔗', '⬇️', '👇', '链接', '自取', '提取', '保存']
    ]

    if not valid_sentences:
        valid_sentences = [text]

    # 1. 语义近义词替换（有几率替换核心词）
    rewritten_sentences = []
    for sent in valid_sentences:
        cur_sent = sent
        for key, synonyms in SYNONYMS_MAP.items():
            if key in cur_sent and random.random() < 0.75:
                replacement = random.choice(synonyms)
                cur_sent = cur_sent.replace(key, replacement, 1)
        rewritten_sentences.append(cur_sent)

    # 2. 组装成推特二创风格排版
    parts = []
    # 顶部爆款标题钩子
    parts.append(random.choice(PREFIX_HOOKS))
    parts.append("")

    # 第一段：主打亮点
    main_highlight = rewritten_sentences[0] if rewritten_sentences else "全套精品资源无套路分享"
    parts.append(f"📌 【核心内容】\n{main_highlight}")

    # 第二段：特色功能/细节亮点
    if len(rewritten_sentences) > 1:
        points = []
        point_emojis = ["✅", "💻", "⚡", "✨", "🎯"]
        for i, sub in enumerate(rewritten_sentences[1:4]):
            emoji_icon = point_emojis[i % len(point_emojis)]
            points.append(f"{emoji_icon} {sub}")
        parts.append("\n" + "\n".join(points))

    # 第三段：平台适配说明
    plat_name = "夸克网盘" if platform == "quark" else "百度网盘"
    parts.append(f"\n📦 存储于：{plat_name}（极速一键转存）")

    # 第四段：直接植入分享链接
    if share_link:
        link_str = f"🔗 资源链接：{share_link}"
        if passcode:
            link_str += f" 🔑 提取码：{passcode}"
        parts.append("\n" + link_str)

    # 结尾 CTA
    parts.append(random.choice(CLOSING_CTAS))

    return "\n".join(parts).strip()


def generate_copy_from_files(
    title: str = "",
    files: Optional[List[Dict[str, Any]]] = None,
    file_count: int = 0,
    total_size: int = 0,
    platform: str = "quark",
    share_link: str = "",
    passcode: str = ""
) -> str:
    """
    根据网盘转存提取到的文件信息，本地智能构建二创文案
    """
    files = files or []
    category = detect_category(files)
    display_title = clean_title(title)

    emojis = CATEGORY_EMOJIS.get(category, []) + CATEGORY_EMOJIS['general']
    emoji = random.choice(emojis)

    parts = []
    # 1. 标题吸引点
    hook = random.choice(OPENING_HOOKS).format(emoji=emoji, title=display_title)
    parts.append(hook)
    parts.append("")

    # 2. 详细特性
    cat_templates = CATEGORY_TEMPLATES.get(category, CATEGORY_TEMPLATES['general'])
    desc = random.choice(cat_templates)
    parts.append(f"💡 特色亮点：\n{desc}")

    # 3. 文件规格概览
    actual_count = file_count or len(files)
    computed_size = total_size
    if computed_size <= 0 and files:
        computed_size = sum(f.get('size', f.get('file_size', 0)) or 0 for f in files)

    info_items = []
    if actual_count > 1:
        info_items.append(f"共包含 {actual_count} 个文件")
    if computed_size > 0:
        info_items.append(f"总容量约 {format_size(computed_size)}")

    plat_name = "夸克网盘" if platform == "quark" else "百度网盘"
    if info_items:
        parts.append(f"📂 资源规格：{' · '.join(info_items)}（{plat_name}）")
    else:
        parts.append(f"📂 资源渠道：{plat_name}一键转存")

    # 4. 直接植入分享链接
    if share_link:
        link_str = f"🔗 资源链接：{share_link}"
        if passcode:
            link_str += f" 🔑 提取码：{passcode}"
        parts.append("\n" + link_str)

    # 5. CTA
    parts.append(random.choice(CLOSING_CTAS))

    return "\n".join(parts).strip()


def generate_copy(
    title: str = "",
    files: Optional[List[Dict[str, Any]]] = None,
    file_count: int = 0,
    total_size: int = 0,
    platform: str = "quark",
    original_text: str = "",
    share_link: str = "",
    passcode: str = ""
) -> str:
    """
    综合文案生成入口：
    - 若传入了原帖文案：优先基于原帖文案执行本地语义二创改写
    - 若未传入原帖文案或只有纯链接：根据文件信息构建二创文案
    同时将真实分享链接直接集成到文案中
    """
    if original_text and len(original_text.strip()) > 3:
        return rewrite_text_locally(
            original_text,
            platform=platform,
            share_link=share_link,
            passcode=passcode
        )
    else:
        return generate_copy_from_files(
            title=title,
            files=files,
            file_count=file_count,
            total_size=total_size,
            platform=platform,
            share_link=share_link,
            passcode=passcode
        )
