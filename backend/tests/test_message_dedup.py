"""
消息去重逻辑测试

覆盖场景：
1. 首次识别 - 记录基线，不报新消息
2. 正常追加新消息
3. 重复消息 (A, B, B) - 必须正确识别多个相同内容
4. 滚动场景 - 旧消息滑出屏幕
5. AI 识别差异 - 部分消息不完全匹配
6. 完全无重叠 - 可能切换了聊天
7. 边界情况
"""

import pytest
from ai.processor import AIMessageProcessor


# 辅助函数：创建消息元组
def msg(sender: str, content: str) -> tuple[str, str]:
    """创建消息元组"""
    return (sender, content)


def msgs(*items: str) -> list[tuple[str, str]]:
    """快速创建消息列表，格式: "sender:content" """
    result = []
    for item in items:
        if ":" in item:
            sender, content = item.split(":", 1)
            result.append((sender.strip(), content.strip()))
        else:
            result.append(("", item.strip()))
    return result


class TestFindNewMessagesBySuffixMatch:
    """测试 _find_new_messages_by_suffix_match 方法"""

    @pytest.fixture
    def processor(self):
        """创建处理器实例（不启用 AI）"""
        return AIMessageProcessor(api_key="", enable_ai=False)

    # ==================== 基本场景 ====================

    def test_empty_history(self, processor):
        """空历史应返回空列表"""
        history = []
        current = msgs("A:你好", "B:世界")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == []

    def test_empty_current(self, processor):
        """空当前应返回空列表"""
        history = msgs("A:你好", "B:世界")
        current = []
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == []

    def test_no_new_messages(self, processor):
        """没有新消息"""
        history = msgs("A:你好", "B:世界")
        current = msgs("A:你好", "B:世界")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == []

    # ==================== 正常追加场景 ====================

    def test_append_single_message(self, processor):
        """追加单条消息"""
        history = msgs("A:你好", "B:世界")
        current = msgs("A:你好", "B:世界", "C:新消息")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("C:新消息")

    def test_append_multiple_messages(self, processor):
        """追加多条消息"""
        history = msgs("A:消息1", "B:消息2")
        current = msgs("A:消息1", "B:消息2", "C:消息3", "D:消息4")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("C:消息3", "D:消息4")

    # ==================== 重复消息场景（核心测试）====================

    def test_duplicate_content_single_new(self, processor):
        """重复内容：A, B -> A, B, B（新增一个 B）"""
        history = msgs("用户:A", "用户:B")
        current = msgs("用户:A", "用户:B", "用户:B")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("用户:B")
        assert len(result) == 1  # 只有一个新 B

    def test_duplicate_content_multiple_new(self, processor):
        """重复内容：A, B -> A, B, B, B（新增两个 B）"""
        history = msgs("用户:A", "用户:B")
        current = msgs("用户:A", "用户:B", "用户:B", "用户:B")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("用户:B", "用户:B")
        assert len(result) == 2  # 两个新 B

    def test_duplicate_in_history_new_different(self, processor):
        """历史有重复，新消息不同：A, B, B -> A, B, B, C"""
        history = msgs("用户:A", "用户:B", "用户:B")
        current = msgs("用户:A", "用户:B", "用户:B", "用户:C")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("用户:C")

    def test_duplicate_in_both(self, processor):
        """历史和当前都有重复：A, B, B -> A, B, B, B"""
        history = msgs("用户:A", "用户:B", "用户:B")
        current = msgs("用户:A", "用户:B", "用户:B", "用户:B")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("用户:B")
        assert len(result) == 1

    def test_three_same_messages(self, processor):
        """连续三条相同消息：A -> A, B, B, B"""
        history = msgs("用户:A")
        current = msgs("用户:A", "用户:B", "用户:B", "用户:B")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("用户:B", "用户:B", "用户:B")
        assert len(result) == 3

    # ==================== 滚动场景 ====================

    def test_scroll_simple(self, processor):
        """简单滚动：旧消息滑出"""
        history = msgs("A:1", "B:2", "C:3", "D:4")
        current = msgs("C:3", "D:4", "E:5", "F:6")  # A, B 滑出
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("E:5", "F:6")

    def test_scroll_with_duplicate(self, processor):
        """滚动 + 重复消息"""
        history = msgs("A:1", "B:2", "B:2", "C:3")
        current = msgs("B:2", "C:3", "D:4", "D:4")  # A 和第一个 B:2 滑出
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("D:4", "D:4")
        assert len(result) == 2

    def test_scroll_large(self, processor):
        """大量滚动：只有一条重叠"""
        history = msgs("A:1", "B:2", "C:3", "D:4", "E:5")
        current = msgs("E:5", "F:6", "G:7", "H:8")  # 只有 E:5 重叠
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("F:6", "G:7", "H:8")

    # ==================== 部分后缀匹配（完整序列不匹配，单条能匹配）====================

    def test_partial_suffix_match(self, processor):
        """部分后缀匹配：完整序列不匹配，但单条后缀能匹配"""
        # AI 把 "你好" 识别成了 "你好！"（多了感叹号）
        history = msgs("A:你好", "B:世界")
        current = msgs("A:你好！", "B:世界", "C:新消息")  # 第一条有差异
        # 后缀 [A:你好, B:世界] 不匹配，但 [B:世界] 能匹配
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("C:新消息")

    # ==================== 锚点匹配（历史最后几条都不在当前中）====================

    def test_no_suffix_overlap_uses_anchor(self, processor):
        """无后缀重叠：使用锚点匹配找到历史中的消息"""
        # 场景：消息完全滚动过去，当前截图内容和历史没有连续重叠
        history = msgs("A:1", "B:2", "C:3")
        current = msgs("B:2", "X:新", "Y:新2")  # B:2 存在于历史中，可作为锚点
        # 后缀匹配失败后，锚点匹配找到 B:2，返回其后的消息
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("X:新", "Y:新2")

    # ==================== 完全无重叠 ====================

    def test_no_overlap_returns_last(self, processor):
        """完全无重叠时保守返回最后一条（避免误报）"""
        history = msgs("A:旧1", "B:旧2")
        current = msgs("X:新1", "Y:新2", "Z:新3")
        result = processor._find_new_messages_by_suffix_match(history, current)
        # 无法确定匹配位置时，保守只返回最后一条
        assert result == msgs("Z:新3")


class TestMergeHistory:
    """测试 _merge_history 方法"""

    @pytest.fixture
    def processor(self):
        return AIMessageProcessor(api_key="", enable_ai=False)

    # ==================== 基本场景 ====================

    def test_empty_history(self, processor):
        """空历史"""
        history = []
        current = msgs("A:1", "B:2")
        result = processor._merge_history(history, current)
        assert result == msgs("A:1", "B:2")

    def test_empty_current(self, processor):
        """空当前"""
        history = msgs("A:1", "B:2")
        current = []
        result = processor._merge_history(history, current)
        assert result == msgs("A:1", "B:2")

    def test_identical(self, processor):
        """历史和当前完全相同"""
        history = msgs("A:1", "B:2")
        current = msgs("A:1", "B:2")
        result = processor._merge_history(history, current)
        assert result == msgs("A:1", "B:2")

    # ==================== 正常追加 ====================

    def test_append_messages(self, processor):
        """正常追加消息"""
        history = msgs("A:1", "B:2")
        current = msgs("A:1", "B:2", "C:3", "D:4")
        result = processor._merge_history(history, current)
        assert result == msgs("A:1", "B:2", "C:3", "D:4")

    # ==================== 滚动场景 ====================

    def test_scroll_merge(self, processor):
        """滚动场景：保留滑出的旧消息"""
        history = msgs("A:1", "B:2", "C:3", "D:4")
        current = msgs("C:3", "D:4", "E:5", "F:6")  # A, B 滑出
        result = processor._merge_history(history, current)
        assert result == msgs("A:1", "B:2", "C:3", "D:4", "E:5", "F:6")

    def test_scroll_with_duplicate(self, processor):
        """滚动 + 重复消息"""
        history = msgs("A:1", "B:2", "B:2", "C:3")
        current = msgs("B:2", "C:3", "D:4", "D:4")
        result = processor._merge_history(history, current)
        # 期望：保留历史的 A:1, B:2, B:2, C:3，追加新的 D:4, D:4
        assert result == msgs("A:1", "B:2", "B:2", "C:3", "D:4", "D:4")

    # ==================== 重复消息场景 ====================

    def test_duplicate_content_merge(self, processor):
        """重复内容合并"""
        history = msgs("用户:A", "用户:B")
        current = msgs("用户:A", "用户:B", "用户:B")
        result = processor._merge_history(history, current)
        assert result == msgs("用户:A", "用户:B", "用户:B")

    def test_duplicate_no_loss(self, processor):
        """确保重复消息不丢失"""
        history = msgs("用户:A", "用户:B", "用户:B")
        current = msgs("用户:A", "用户:B", "用户:B", "用户:B")
        result = processor._merge_history(history, current)
        # 应该有 3 个 B
        b_count = sum(1 for s, c in result if c == "B")
        assert b_count == 3

    # ==================== 部分后缀匹配场景 ====================

    def test_partial_suffix_merge(self, processor):
        """部分后缀匹配合并：完整序列不匹配，单条能匹配"""
        history = msgs("A:你好", "B:世界")
        current = msgs("A:你好！", "B:世界", "C:新消息")  # A 有差异
        result = processor._merge_history(history, current)
        # 后缀 [B:世界] 匹配，合并后应该是 history + [C:新消息]
        assert result == msgs("A:你好", "B:世界", "C:新消息")

    # ==================== 完全无重叠 ====================

    def test_no_overlap_append_last(self, processor):
        """完全无重叠时追加最后一条新消息"""
        history = msgs("A:旧1", "B:旧2")
        current = msgs("X:新1", "Y:新2")
        result = processor._merge_history(history, current)
        # 无法确定匹配位置时，保守只追加最后一条
        assert result == msgs("A:旧1", "B:旧2", "Y:新2")

    # ==================== 大小限制 ====================

    def test_max_size_limit(self, processor):
        """超过最大大小时截断"""
        history = [msg("用户", str(i)) for i in range(100)]
        current = [msg("用户", str(i)) for i in range(90, 150)]
        result = processor._merge_history(history, current, max_size=50)
        assert len(result) == 50
        # 应该保留最新的 50 条
        assert result[-1] == msg("用户", "149")


class TestLocalDedup:
    """测试 _local_dedup 方法（端到端）"""

    @pytest.fixture
    def processor(self):
        return AIMessageProcessor(api_key="", enable_ai=False)

    def test_first_scan_no_new(self, processor):
        """首次扫描不报新消息"""
        result = processor._local_dedup("测试联系人", msgs("A:1", "B:2", "C:3"))
        assert result == []  # 首次不报

    def test_second_scan_with_new(self, processor):
        """第二次扫描识别新消息"""
        processor._local_dedup("测试联系人", msgs("A:1", "B:2"))
        result = processor._local_dedup("测试联系人", msgs("A:1", "B:2", "C:3"))
        assert result == msgs("C:3")

    def test_duplicate_flow(self, processor):
        """完整的重复消息流程"""
        contact = "测试联系人"

        # 第一次：A
        r1 = processor._local_dedup(contact, msgs("用户:A"))
        assert r1 == []  # 首次不报

        # 第二次：A, B
        r2 = processor._local_dedup(contact, msgs("用户:A", "用户:B"))
        assert r2 == msgs("用户:B")

        # 第三次：A, B, B（新增一个 B）
        r3 = processor._local_dedup(contact, msgs("用户:A", "用户:B", "用户:B"))
        assert r3 == msgs("用户:B")
        assert len(r3) == 1  # 只有一个新 B

        # 第四次：A, B, B, B（再增一个 B）
        r4 = processor._local_dedup(contact, msgs("用户:A", "用户:B", "用户:B", "用户:B"))
        assert r4 == msgs("用户:B")
        assert len(r4) == 1

    def test_scroll_flow(self, processor):
        """滚动场景完整流程"""
        contact = "测试联系人"

        # 初始：A, B, C, D
        processor._local_dedup(contact, msgs("A:1", "B:2", "C:3", "D:4"))

        # 滚动：C, D, E, F（A, B 滑出）
        result = processor._local_dedup(contact, msgs("C:3", "D:4", "E:5", "F:6"))
        assert result == msgs("E:5", "F:6")

        # 再滚动：E, F, G, H（C, D 滑出）
        result = processor._local_dedup(contact, msgs("E:5", "F:6", "G:7", "H:8"))
        assert result == msgs("G:7", "H:8")

    def test_scroll_with_duplicate_flow(self, processor):
        """滚动 + 重复消息流程"""
        contact = "测试联系人"

        # 初始：A, B, B, C
        processor._local_dedup(contact, msgs("用户:A", "用户:B", "用户:B", "用户:C"))

        # 滚动 + 新重复：B, C, D, D（A 和第一个 B 滑出）
        result = processor._local_dedup(contact, msgs("用户:B", "用户:C", "用户:D", "用户:D"))
        assert result == msgs("用户:D", "用户:D")
        assert len(result) == 2  # 两个 D

    def test_history_preserved_after_scroll(self, processor):
        """滚动后历史应该保留滑出的消息"""
        contact = "测试联系人"

        # 初始
        processor._local_dedup(contact, msgs("A:1", "B:2", "C:3"))

        # 滚动
        processor._local_dedup(contact, msgs("C:3", "D:4", "E:5"))

        # 检查历史
        history = processor._message_history.get(contact, [])
        # 应该包含 A:1, B:2（滑出的）和 C:3, D:4, E:5（当前的）
        assert msg("A", "1") in history
        assert msg("B", "2") in history
        assert msg("E", "5") in history


class TestFindSequence:
    """测试 _find_sequence 方法"""

    @pytest.fixture
    def processor(self):
        return AIMessageProcessor(api_key="", enable_ai=False)

    def test_find_at_start(self, processor):
        """在开头找到"""
        messages = msgs("A:1", "B:2", "C:3")
        sequence = msgs("A:1", "B:2")
        assert processor._find_sequence(messages, sequence) == 0

    def test_find_at_middle(self, processor):
        """在中间找到"""
        messages = msgs("A:1", "B:2", "C:3", "D:4")
        sequence = msgs("B:2", "C:3")
        assert processor._find_sequence(messages, sequence) == 1

    def test_find_at_end(self, processor):
        """在结尾找到"""
        messages = msgs("A:1", "B:2", "C:3")
        sequence = msgs("B:2", "C:3")
        assert processor._find_sequence(messages, sequence) == 1

    def test_not_found(self, processor):
        """找不到"""
        messages = msgs("A:1", "B:2", "C:3")
        sequence = msgs("X:1", "Y:2")
        assert processor._find_sequence(messages, sequence) == -1

    def test_empty_sequence(self, processor):
        """空序列"""
        messages = msgs("A:1", "B:2")
        sequence = []
        assert processor._find_sequence(messages, sequence) == -1

    def test_sequence_longer_than_messages(self, processor):
        """序列比消息列表长"""
        messages = msgs("A:1")
        sequence = msgs("A:1", "B:2")
        assert processor._find_sequence(messages, sequence) == -1

    def test_find_duplicate_sequence(self, processor):
        """找重复序列（返回第一个）"""
        messages = msgs("A:1", "B:2", "A:1", "B:2", "C:3")
        sequence = msgs("A:1", "B:2")
        assert processor._find_sequence(messages, sequence) == 0  # 返回第一个


class TestNormalizeText:
    """文本标准化测试（忽略标点符号和 emoji）"""

    @pytest.fixture
    def processor(self):
        return AIMessageProcessor(api_key="", enable_ai=False)

    # ==================== 标点符号标准化 ====================

    def test_normalize_period(self, processor):
        """标准化：英文句号 vs 中文句号"""
        assert processor._normalize_text("无趣.") == processor._normalize_text("无趣。")

    def test_normalize_exclamation(self, processor):
        """标准化：英文感叹号 vs 中文感叹号"""
        assert processor._normalize_text("test!") == processor._normalize_text("test！")

    def test_normalize_question(self, processor):
        """标准化：英文问号 vs 中文问号"""
        assert processor._normalize_text("你好?") == processor._normalize_text("你好？")

    def test_normalize_mixed_punctuation(self, processor):
        """标准化：混合标点"""
        assert processor._normalize_text("用户.名!") == processor._normalize_text("用户。名！")

    def test_normalize_empty(self, processor):
        """标准化：空字符串"""
        assert processor._normalize_text("") == ""

    def test_normalize_only_punctuation(self, processor):
        """标准化：只有标点符号"""
        assert processor._normalize_text("...") == ""
        assert processor._normalize_text("。。。") == ""
        assert processor._normalize_text("!?~") == ""

    # ==================== Emoji 标准化 ====================

    def test_normalize_emoji_smile(self, processor):
        """标准化：不同笑脸 emoji"""
        assert processor._normalize_text("好的😄") == processor._normalize_text("好的😊")
        assert processor._normalize_text("好的😄") == processor._normalize_text("好的")

    def test_normalize_emoji_thumbs(self, processor):
        """标准化：点赞 emoji"""
        assert processor._normalize_text("OK👍") == processor._normalize_text("OK👌")
        assert processor._normalize_text("OK👍") == processor._normalize_text("OK")

    def test_normalize_emoji_heart(self, processor):
        """标准化：爱心 emoji（带变体选择符）"""
        assert processor._normalize_text("收到❤️") == processor._normalize_text("收到")
        assert processor._normalize_text("收到❤️") == processor._normalize_text("收到💕")

    def test_normalize_emoji_laugh(self, processor):
        """标准化：笑哭 emoji"""
        assert processor._normalize_text("哈哈哈😂") == processor._normalize_text("哈哈哈🤣")
        assert processor._normalize_text("哈哈哈😂😂😂") == processor._normalize_text("哈哈哈")

    def test_normalize_emoji_sun(self, processor):
        """标准化：太阳 emoji"""
        assert processor._normalize_text("早上好🌞") == processor._normalize_text("早上好☀️")

    def test_normalize_only_emoji(self, processor):
        """标准化：只有 emoji"""
        assert processor._normalize_text("😄😄😄") == ""
        assert processor._normalize_text("👍🎉❤️") == ""

    def test_normalize_emoji_in_middle(self, processor):
        """标准化：emoji 在中间"""
        assert processor._normalize_text("你好😄世界") == processor._normalize_text("你好世界")

    # ==================== 混合场景 ====================

    def test_normalize_punctuation_and_emoji(self, processor):
        """标准化：同时包含标点和 emoji"""
        assert processor._normalize_text("你好！😄") == processor._normalize_text("你好")
        assert processor._normalize_text("OK!👍") == processor._normalize_text("OK")

    def test_normalize_preserves_content(self, processor):
        """标准化：保留核心内容"""
        assert processor._normalize_text("你好😄") == "你好"
        assert processor._normalize_text("Hello World!") == "Hello World"
        assert processor._normalize_text("测试123") == "测试123"

    def test_normalize_whitespace(self, processor):
        """标准化：空白字符处理"""
        assert processor._normalize_text("你好  世界") == "你好 世界"
        assert processor._normalize_text("  你好  ") == "你好"

    def test_messages_equal_same_sender(self, processor):
        """消息相等：相同发送者"""
        msg1 = ("无趣.", "你好")
        msg2 = ("无趣.", "你好")
        assert processor._messages_equal(msg1, msg2)

    def test_messages_equal_sender_punctuation_diff(self, processor):
        """消息相等：发送者标点不同"""
        msg1 = ("无趣.", "你好")
        msg2 = ("无趣。", "你好")
        assert processor._messages_equal(msg1, msg2)

    def test_messages_not_equal_content_diff(self, processor):
        """消息不相等：内容不同"""
        msg1 = ("无趣.", "你好")
        msg2 = ("无趣.", "世界")
        assert not processor._messages_equal(msg1, msg2)

    def test_find_sequence_with_punctuation_diff(self, processor):
        """序列查找：发送者标点不一致"""
        # 历史中是英文句号，当前识别成中文句号
        messages = [("无趣。", "A"), ("无趣。", "B"), ("无趣。", "C")]
        sequence = [("无趣.", "A"), ("无趣.", "B")]  # 英文句号
        assert processor._find_sequence(messages, sequence) == 0

    def test_dedup_with_punctuation_diff(self, processor):
        """去重：发送者标点不一致"""
        contact = "测试联系人"

        # 第一次识别：英文句号
        processor._local_dedup(contact, [("无趣.", "消息1"), ("无趣.", "消息2")])

        # 第二次识别：中文句号（AI 识别不一致）
        result = processor._local_dedup(
            contact,
            [("无趣。", "消息1"), ("无趣。", "消息2"), ("无趣。", "消息3")]
        )
        # 应该正确识别出新消息，不应该因为标点不一致而把全部消息当作新消息
        assert len(result) == 1
        assert result[0][1] == "消息3"

    def test_dedup_mixed_punctuation(self, processor):
        """去重：混合标点场景"""
        contact = "测试联系人"

        # 初始消息有多种标点符号的昵称
        processor._local_dedup(contact, [
            ("张三.", "你好"),
            ("李四!", "世界"),
        ])

        # AI 识别时标点不一致
        result = processor._local_dedup(contact, [
            ("张三。", "你好"),  # 句号变中文
            ("李四！", "世界"),  # 感叹号变中文
            ("王五", "新消息"),
        ])

        # 应该只有 "新消息" 是新的
        assert len(result) == 1
        assert result[0] == ("王五", "新消息")

    # ==================== Emoji 去重端到端测试 ====================

    def test_dedup_emoji_in_content(self, processor):
        """去重：消息内容 emoji 不一致"""
        contact = "测试联系人"

        # 第一次识别：带 emoji
        processor._local_dedup(contact, [
            ("张三", "好的😄"),
            ("李四", "收到👍"),
        ])

        # 第二次识别：emoji 不一致或缺失
        result = processor._local_dedup(contact, [
            ("张三", "好的😊"),  # 😄 变成 😊
            ("李四", "收到"),    # 👍 丢失
            ("王五", "新消息"),
        ])

        # 应该只有 "新消息" 是新的
        assert len(result) == 1
        assert result[0] == ("王五", "新消息")

    def test_dedup_emoji_added_by_ai(self, processor):
        """去重：AI 多识别出 emoji"""
        contact = "测试联系人"

        # 第一次识别：无 emoji
        processor._local_dedup(contact, [
            ("张三", "好的"),
            ("李四", "收到"),
        ])

        # 第二次识别：AI 多识别出 emoji
        result = processor._local_dedup(contact, [
            ("张三", "好的😄"),  # 多了 😄
            ("李四", "收到❤️"),  # 多了 ❤️
            ("王五", "真棒🎉"),
        ])

        # 应该只有 "真棒🎉" 是新的
        assert len(result) == 1
        assert result[0][1] in ("真棒🎉", "真棒")  # 标准化后相等

    def test_dedup_multiple_emoji_variations(self, processor):
        """去重：多个 emoji 变化"""
        contact = "测试联系人"

        # 第一次识别
        processor._local_dedup(contact, [
            ("用户", "哈哈哈😂😂😂"),
        ])

        # 第二次识别：emoji 数量或类型不同
        result = processor._local_dedup(contact, [
            ("用户", "哈哈哈🤣"),  # 😂😂😂 变成 🤣
            ("用户", "新消息"),
        ])

        # 应该只有 "新消息" 是新的
        assert len(result) == 1
        assert result[0][1] == "新消息"

    def test_dedup_emoji_with_punctuation(self, processor):
        """去重：emoji + 标点同时不一致"""
        contact = "测试联系人"

        # 第一次识别
        processor._local_dedup(contact, [
            ("无趣.", "你好!😄"),
        ])

        # 第二次识别：发送者标点、内容标点、emoji 都不一致
        result = processor._local_dedup(contact, [
            ("无趣。", "你好！😊"),  # 全部不一致
            ("无趣", "新消息"),
        ])

        # 应该只有 "新消息" 是新的
        assert len(result) == 1
        assert result[0][1] == "新消息"


class TestEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def processor(self):
        return AIMessageProcessor(api_key="", enable_ai=False)

    def test_single_message_history(self, processor):
        """单条消息历史"""
        history = msgs("A:1")
        current = msgs("A:1", "B:2")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("B:2")

    def test_single_message_current(self, processor):
        """单条当前消息"""
        history = msgs("A:1", "B:2")
        current = msgs("B:2")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == []

    def test_all_same_content(self, processor):
        """所有消息内容相同"""
        history = msgs("用户:哈", "用户:哈", "用户:哈")
        current = msgs("用户:哈", "用户:哈", "用户:哈", "用户:哈")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("用户:哈")
        assert len(result) == 1

    def test_unicode_content(self, processor):
        """Unicode 内容"""
        history = msgs("张三:你好👋", "李四:世界🌍")
        current = msgs("张三:你好👋", "李四:世界🌍", "王五:新年快乐🎉")
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == msgs("王五:新年快乐🎉")

    def test_multiline_content(self, processor):
        """多行内容"""
        history = [("用户", "第一行\n第二行")]
        current = [("用户", "第一行\n第二行"), ("用户", "新消息")]
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == [("用户", "新消息")]

    def test_empty_sender(self, processor):
        """空发送者"""
        history = [("", "消息1"), ("", "消息2")]
        current = [("", "消息1"), ("", "消息2"), ("", "消息3")]
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == [("", "消息3")]

    def test_whitespace_in_content(self, processor):
        """内容中有空白字符"""
        history = [("用户", "你好  世界")]  # 两个空格
        current = [("用户", "你好  世界"), ("用户", "新消息")]
        result = processor._find_new_messages_by_suffix_match(history, current)
        assert result == [("用户", "新消息")]


class TestRealWorldScenarios:
    """真实场景模拟测试"""

    @pytest.fixture
    def processor(self):
        return AIMessageProcessor(api_key="", enable_ai=False)

    def test_typical_chat_flow(self, processor):
        """典型聊天流程"""
        contact = "朋友"

        # 开始聊天
        processor._local_dedup(contact, msgs("我:你好", "朋友:你好呀"))

        # 对方回复
        r1 = processor._local_dedup(contact, msgs("我:你好", "朋友:你好呀", "朋友:在干嘛"))
        assert r1 == msgs("朋友:在干嘛")

        # 我回复
        r2 = processor._local_dedup(contact, msgs("朋友:你好呀", "朋友:在干嘛", "我:写代码"))
        assert r2 == msgs("我:写代码")

        # 对方连发两条
        r3 = processor._local_dedup(
            contact,
            msgs("朋友:在干嘛", "我:写代码", "朋友:哦哦", "朋友:加油")
        )
        assert r3 == msgs("朋友:哦哦", "朋友:加油")

    def test_spam_same_message(self, processor):
        """刷屏场景：连续发送相同消息"""
        contact = "群聊"

        # 初始
        processor._local_dedup(contact, msgs("A:1"))

        # 连发三个 "哈哈"
        r1 = processor._local_dedup(
            contact,
            msgs("A:1", "B:哈哈", "B:哈哈", "B:哈哈")
        )
        assert len(r1) == 3
        assert all(c == "哈哈" for _, c in r1)

        # 再发两个 "哈哈"
        r2 = processor._local_dedup(
            contact,
            msgs("B:哈哈", "B:哈哈", "B:哈哈", "B:哈哈", "B:哈哈")
        )
        assert len(r2) == 2

    def test_long_conversation_scroll(self, processor):
        """长对话滚动场景"""
        contact = "长对话"

        # 模拟 50 条消息
        initial = [(f"用户{i%3}", f"消息{i}") for i in range(50)]
        processor._local_dedup(contact, initial)

        # 滚动，只显示最后 20 条 + 5 条新消息
        current = initial[-20:] + [(f"用户{i%3}", f"消息{i}") for i in range(50, 55)]
        result = processor._local_dedup(contact, current)

        # 应该识别出 5 条新消息
        assert len(result) == 5
        assert result[0] == ("用户2", "消息50")
        assert result[-1] == ("用户0", "消息54")
