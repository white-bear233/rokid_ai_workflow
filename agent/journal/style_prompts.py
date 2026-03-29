"""游记风格提示词模板

两个维度的组合控制：
- writing_style: 文艺/幽默/简洁/故事 — 控制文字风格和修辞
- user_mode: 默认模式/亲子模式/情侣模式 — 控制内容侧重点和情感基调
"""

# ==================== 写作风格提示词 ====================

WRITING_STYLE_PROMPTS = {
    "文艺": {
        "tone": "优美、诗意、感性，善用比喻和修辞",
        "length": "80-100字",
        "features": [
            "善用比喻、排比、拟人等修辞手法",
            "注重光影、色彩、声音等感官描写",
            "融入历史典故和文化内涵",
            "情感细腻，富有诗意",
            "结尾常有哲理性的感悟"
        ],
        "example": "晨曦中的古城，仿佛一位从历史深处走来的老者，静静地诉说着千年的沧桑。青石板上的每一道裂痕，都是岁月留下的印记。",
        "forbidden": [
            "过度堆砌华丽辞藻",
            "无意义的抒情",
            "与照片内容无关的描写"
        ]
    },

    "幽默": {
        "tone": "轻松、有趣、调侃，适当自嘲",
        "length": "80-100字",
        "features": [
            "适当自嘲，制造轻松氛围",
            "用网络流行语（适量）",
            "吐槽旅途中的小插曲",
            "发现景点的'槽点'但不恶意贬低",
            "结尾常有点睛之笔的幽默"
        ],
        "example": "本以为是'天下第一险峰'，结果爬上去发现...还有卖烤肠的。不过这烤肠是真香，建议来之前别吃早饭。",
        "forbidden": [
            "低俗笑话",
            "恶意攻击景点或他人",
            "过度负面评价"
        ]
    },

    "简洁": {
        "tone": "干练、直接、实用，重点突出",
        "length": "60-80字",
        "features": [
            "重点突出，不拖泥带水",
            "实用信息优先（交通、门票、时间）",
            "简短的个人评价",
            "条理清晰，易于阅读",
            "适当的建议和提醒"
        ],
        "example": "黄山风景区：索道上山180元，建议早上7点前到达避开人流。光明顶看日出最佳，需提前1小时占位。山顶住宿600起，淡季可砍价。",
        "forbidden": [
            "过多抒情和描写",
            "无用的废话",
            "冗长的叙述"
        ]
    },

    "故事": {
        "tone": "叙事、连贯、引人入胜，像讲故事",
        "length": "80-100字",
        "features": [
            "有清晰的时间线和情节",
            "设置悬念和高潮",
            "人物对话和场景描写结合",
            "首尾呼应，结构完整",
            "融入个人成长或感悟"
        ],
        "example": "那是一个雾气弥漫的清晨，我独自一人踏上了通往山顶的小径。谁知这一走，竟让我遇到了改变这次旅程的那个人...",
        "forbidden": [
            "虚构不存在的事件",
            "过度夸张",
            "与实际照片内容冲突"
        ]
    }
}


# ==================== 用户模式提示词 ====================

USER_MODE_PROMPTS = {
    "默认模式": {
        "tone": "专业、准确、客观",
        "focus": "景点介绍、实用信息、旅行体验",
        "perspective": "第三人称或第一人称均可",
        "keywords": ["历史", "特色", "体验", "建议"],
        "example": "大雁塔建于唐高宗永徽三年，是玄奘法师翻译佛经的场所。塔高64米，共七层，是西安的标志性建筑之一。"
    },

    "亲子模式": {
        "tone": "活泼、亲切、童趣",
        "focus": "适合小朋友的发现、有趣的互动、成长体验",
        "perspective": "家长视角（'宝贝'、'小朋友'）",
        "keywords": ["发现", "互动", "成长", "有趣", "可爱"],
        "example": "宝贝今天在大雁塔广场看到了好多鸽子，追着跑了好久都不想走。还学到了玄奘法师西天取经的故事，说以后也要当个勇敢的探险家！"
    },

    "情侣模式": {
        "tone": "浪漫、温柔、细腻",
        "focus": "两人的互动、浪漫瞬间、情感回忆",
        "perspective": "情侣视角（'我们'、'一起'）",
        "keywords": ["浪漫", "温馨", "回忆", "甜蜜", "相伴"],
        "example": "夕阳下的大雁塔格外温柔，我们并肩坐在台阶上，看喷泉升起的水雾染成金色。这一刻，时光仿佛静止，只有音乐和水声在耳边回响。"
    }
}


# ==================== 组合提示词生成 ====================

def get_combined_prompt(writing_style: str, user_mode: str) -> dict:
    """
    获取写作风格和用户模式的组合提示词

    Args:
        writing_style: 写作风格（文艺/幽默/简洁/故事）
        user_mode: 用户模式（默认模式/亲子模式/情侣模式）

    Returns:
        dict: 组合后的提示词配置
    """
    style_config = WRITING_STYLE_PROMPTS.get(writing_style, WRITING_STYLE_PROMPTS["文艺"])
    mode_config = USER_MODE_PROMPTS.get(user_mode, USER_MODE_PROMPTS["默认模式"])

    return {
        "writing_style": writing_style,
        "user_mode": user_mode,
        "tone": f"{style_config['tone']}，{mode_config['tone']}",
        "focus": mode_config["focus"],
        "perspective": mode_config["perspective"],
        "length": style_config["length"],
        "features": style_config["features"],
        "keywords": mode_config["keywords"],
        "example": style_config["example"],
        "forbidden": style_config["forbidden"]
    }


def build_system_prompt(writing_style: str, user_mode: str) -> str:
    """
    构建完整的系统提示词

    Args:
        writing_style: 写作风格
        user_mode: 用户模式

    Returns:
        str: 完整的系统提示词
    """
    config = get_combined_prompt(writing_style, user_mode)

    return f"""你是一位专业的旅游游记作家。

【写作风格】: {config['writing_style']}
- 语调: {config['tone']}
- 字数建议: {config['length']}

【用户模式】: {config['user_mode']}
- 内容侧重点: {config['focus']}
- 叙事视角: {config['perspective']}
- 关键词: {', '.join(config['keywords'])}

【写作特点】:
{chr(10).join(f'- {f}' for f in config['features'])}

【禁止事项】:
{chr(10).join(f'- {f}' for f in config['forbidden'])}

【示例】:
{config['example']}

请根据提供的照片信息和叙事结构，生成符合以上要求的游记内容。"""


# ==================== 叙事片段类型 ====================

NARRATIVE_SEGMENT_TYPES = {
    "开篇": {
        "description": "游记开头，引入主题",
        "length_ratio": 0.15,  # 占总字数的比例
        "prompt_hint": "简要介绍这次旅行的背景和期待"
    },
    "写景": {
        "description": "描述景色、建筑、风景",
        "length_ratio": 0.35,
        "prompt_hint": "详细描述旅途中的景色和见闻"
    },
    "抒情": {
        "description": "表达感受、情感",
        "length_ratio": 0.20,
        "prompt_hint": "表达旅行中的感受和情感"
    },
    "感悟": {
        "description": "旅行中的思考、领悟",
        "length_ratio": 0.15,
        "prompt_hint": "分享旅行带来的思考和感悟"
    },
    "结尾": {
        "description": "游记收束，总结或展望",
        "length_ratio": 0.15,
        "prompt_hint": "总结这次旅行的感受，或对下次旅行表达期待"
    }
}


# ==================== 场景类型映射 ====================

SCENE_TYPE_EMOTIONS = {
    "建筑": ["历史", "沧桑", "宏伟", "精致"],
    "自然": ["清新", "宁静", "壮美", "生机"],
    "人物": ["温馨", "欢乐", "感动", "活力"],
    "美食": ["满足", "惊喜", "地道", "回味"],
    "街景": ["烟火", "繁华", "悠闲", "市井"],
    "夜景": ["璀璨", "浪漫", "宁静", "迷人"]
}
