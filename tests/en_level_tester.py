"""英语水平功能测试：用于测试tester模块从生成题目到计算水平的全流程"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到python路径，确保能找到config和tools
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(PROJECT_ROOT))

from tools.level_tester.database import db
from tools.level_tester.english.tester import level_tester
from tools.level_tester.english.coca_loader import coca_loader

async def test_coca_loader():
    """测试1：验证COCA词频库加载"""
    print("\n"+"-"*50)
    print("测试1：coca词频库加载")
    print("-"*50)

    success = coca_loader.load()
    if not success:
        print("COCA词频库加载失败")
        return False

    total = coca_loader.get_total_words()
    print(f"COCA词频库加载成功，单词总数：{total}")

    # 测试各级别单词数量
    print("\n 各级别单词分布：")
    for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        words = coca_loader.get_words_by_level(level)
        threshold = coca_loader.CEFR_THRESHOLDS[level]
        ratio = coca_loader.get_cefr_ratio(level)
        print(f"{level}: {len(words)} 个 (阈值: {threshold}, 累计占比: {ratio:.2%})")

    return True

async def test_generate_questions():
    """测试2：生成测试题目"""
    print("\n"+"-"*50)
    print("测试2: 生成测试题目 (30题)")
    print("-" * 60)

    questions = await level_tester.generate_test("en")

    print(f"生成了{len(questions)} 道测试题")

    # 统计各级别题目数量
    level_counts = {}
    for q in questions:
        level = q.get("level","未知")
        level_counts[level] = level_counts.get(level,0)+1

    print("\n各级别题目分布:")
    for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        count = level_counts.get(level, 0)
        bar = "█" * count + "░" * (5 - count)  # 每级期望5题
        print(f"{level}: {count}题{bar}")

    # 打印前3题示例
    print("\n题目示例 (前3题):")
    for i,q in enumerate(questions[:3],1):
        print(f"\n 第{i}题:")
        print(f"单词:{q.get('word')}")
        print(f"等级:{q.get('level')}")
        print(f"音标:{q.get('phonetic', 'N/A')}")
        print(f"选项:{q.get('options')}")
        print(f"正确答案:{q.get('correct')}")

    return questions

async def test_calculate_level(questions):
    """测试3：计算测试结果"""
    print("\n" + "-" * 50)
    print("测试3: 计算测试结果")
    print("-" * 50)

    # 模拟用户作答（全部选择正确，用于测试最高分场景）
    user_id = "test_user_001"
    language_code = "en"

    for q in questions:
        q["selected"] = q["correct"]

    # 调用计算结果
    level, vocab_size, result = await level_tester.calculate_level(
        user_id="test_user_001",
        language_code="en",
        answers=questions  # questions 中的每个 dict 都包含 rank
    )

    print(f"\n测试结果:")
    print(f"├─ CEFR 等级: {level}")
    print(f"├─ 估算词汇量: {vocab_size:,}")
    print(f"├─ 正确题数: {result['correct_count']}/{result['total_questions']}")
    print(f"└─ 得分率: {result['score_percent']}%")

    # 获取等级描述
    description = level_tester._get_cefr_description(level)
    if description:
        print(f"\n 等级描述: {description}")

    return result


async def test_incorrect_answers():
    """测试4：测试答错部分题目的场景"""
    print("\n"+"-"*50)
    print("测试4: 答错部分题目的场景")
    print("-" * 60)

    questions = await level_tester.generate_test("en")

    # 模拟用户作答：前15题正确，后15题错误
    user_id = "test_user_002"
    language_code = "en"

    for i, q in enumerate(questions):
        if i < 15:
            q["selected"] = q["correct"]  # 正确
        else:
            # 选择一个错误的选项（不是正确答案）
            options = q.get("options", [])
            wrong_options = [opt for opt in options if opt != q.get("correct")]
            q["selected"] = wrong_options[0] if wrong_options else q.get("correct")

    level, vocab_size, result = await level_tester.calculate_level(
        user_id=user_id,
        language_code=language_code,
        answers=questions
    )

    print(f"\n 部分正确的测试结果:")
    print(f"  ├─ CEFR 等级: {level}")
    print(f"  ├─ 估算词汇量: {vocab_size:,}")
    print(f"  ├─ 正确题数: {result['correct_count']}/{result['total_questions']}")
    print(f"  └─ 得分率: {result['score_percent']}%")

    return result

async def test_grade_distribution():
    """测试5: 测试不同等级词汇的权重分布"""
    print("\n" + "-" * 50)
    print("测试5: 不同CEFR等级的权重分布")
    print("-" * 50)

    total_words = coca_loader.get_total_words()
    print(f"\n词库总量: {total_words:,}")
    print("\n等级 | 词汇量阈值 | 累计占比 | 说明")
    print("-" * 40)

    for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        threshold = coca_loader.CEFR_THRESHOLDS[level]
        ratio = coca_loader.get_cefr_ratio(level)
        words_count = len(coca_loader.get_words_by_level(level))
        print(f" {level}  | {threshold:>6,}    | {ratio:>7.2%} | {words_count:>5} 个词")


    # 测试一个具体单词的贡献计算
    print("\n🔍示例: 计算单个单词的贡献值")
    test_ranks = [500, 2000, 5000, 10000, 15000, 19000]

    print("\n词频排名 | CEFR等级 | 累计占比 | 贡献值 (rank/total × 占比)")
    print("-" * 50)

    for rank in test_ranks:
        level = coca_loader.get_level_by_rank(rank)
        ratio = coca_loader.get_cefr_ratio(level)
        contribution = (rank / total_words) * ratio
        print(f"  {rank:>6}  |   {level}     |  {ratio:>7.2%}  |  {contribution:.6f}")


async def main():
    """运行所有测试"""
    print("\n" + "█" * 60)
    print("LaLe英语水平测试模块-完整测试套件")
    print("█" * 60)

    try:
        # 1. 初始化数据库
        print("\n 连接数据库...")
        await db.init_pool()
        print(" 数据库连接成功")

        # 2. 运行所有测试
        test1 = await test_coca_loader()
        if not test1:
            print("\n COCA词频库加载失败，终止测试")
            return

        questions = await test_generate_questions()

        await test_calculate_level(questions)

        await test_incorrect_answers()

        await test_grade_distribution()

        # 3. 测试总结
        print("\n" + "-" * 60)
        print("所有测试完成")
        print("-" * 60)
        print("\n 提示:")
        print("查看数据库level_tests表确认测试结果已保存")
        print("可以通过DataGrip查询: SELECT * FROM level_tests;")

    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭数据库连接
        await db.pool.close()
        print("\n 数据库连接已关闭")


if __name__ == "__main__":
    asyncio.run(main())
















