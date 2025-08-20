#!/usr/bin/env python3
"""
第三阶段第一阶段数据生成器
多维度质量验证的高质量多轮推理对话生成
"""

import sys
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.utils.logging import get_logger
from src.data_preparation.advanced_prompt_templates import AdvancedPromptTemplates, ReasoningType
from src.evaluation.quality_scorer import QualityScorer, QuestionType
from gemini_integration import GeminiDataGenerator


class Phase1DataGenerator:
    """第一阶段数据生成器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("phase1_generator")
        
        # 初始化组件
        self.prompt_generator = AdvancedPromptTemplates()
        self.gemini_generator = GeminiDataGenerator()
        self.quality_scorer = QualityScorer()
        
        # 生成统计
        self.generation_stats = {
            "total_attempted": 0,
            "total_successful": 0,
            "by_type": {
                "math_reasoning": {"attempted": 0, "successful": 0, "failed": 0},
                "multi_hop": {"attempted": 0, "successful": 0, "failed": 0},
                "ambiguity_clarification": {"attempted": 0, "successful": 0, "failed": 0}
            },
            "quality_distribution": {"A": 0, "B": 0, "C": 0},
            "start_time": None,
            "end_time": None
        }
        
        self.logger.info("第一阶段数据生成器初始化完成")
    
    def create_phase1_questions(self) -> List[Dict[str, Any]]:
        """创建第一阶段验证问题集（每类型15个，共45个）"""
        
        # 数学推理问题
        math_questions = [
            {"question": "一个正方形的周长是20厘米，求面积", "type": ReasoningType.MATH_REASONING, "context": "几何计算"},
            {"question": "小明买了3支笔和2本书，总共花了25元，每支笔3元，每本书多少元？", "type": ReasoningType.MATH_REASONING, "context": "应用题"},
            {"question": "一辆车以60公里/小时的速度行驶，需要多长时间到达目的地？", "type": ReasoningType.MATH_REASONING, "context": "速度时间问题"},
            {"question": "计算复利：本金1000元，年利率5%，3年后本息合计多少？", "type": ReasoningType.MATH_REASONING, "context": "金融计算"},
            {"question": "一个圆的半径是多少时面积等于50平方厘米？", "type": ReasoningType.MATH_REASONING, "context": "反向计算"},
            {"question": "张三的年龄是李四的2倍，两人年龄之和是45岁，各自多少岁？", "type": ReasoningType.MATH_REASONING, "context": "年龄问题"},
            {"question": "一批货物，第一天运走全部的1/3，第二天运走余下的1/2，还剩60吨，原来有多少吨？", "type": ReasoningType.MATH_REASONING, "context": "分数应用"},
            {"question": "某商品打8折后价格是160元，原价是多少？", "type": ReasoningType.MATH_REASONING, "context": "折扣计算"},
            {"question": "一个水池，进水管每小时进水20立方米，排水管每小时排水12立方米，多长时间能注满100立方米的水池？", "type": ReasoningType.MATH_REASONING, "context": "工程问题"},
            {"question": "甲乙两地相距240公里，两车同时从两地相对开出，甲车速度80公里/小时，乙车速度多少时能在1.5小时后相遇？", "type": ReasoningType.MATH_REASONING, "context": "相遇问题"},
            {"question": "一个等腰三角形的底边长8厘米，腰长多少时周长为20厘米？", "type": ReasoningType.MATH_REASONING, "context": "几何问题"},
            {"question": "投资股票，第一年亏损20%，第二年盈利多少才能回到本金？", "type": ReasoningType.MATH_REASONING, "context": "投资计算"},
            {"question": "一个数加上它的20%等于36，这个数是多少？", "type": ReasoningType.MATH_REASONING, "context": "百分数问题"},
            {"question": "制作一个长方体盒子，长宽高之比是3:2:1，体积是48立方厘米，各边长是多少？", "type": ReasoningType.MATH_REASONING, "context": "立体几何"},
            {"question": "某工厂原计划20天完成一批产品，实际每天多生产25%，实际需要多少天完成？", "type": ReasoningType.MATH_REASONING, "context": "工作效率"}
        ]
        
        # 多跳推理问题
        multi_hop_questions = [
            {"question": "世界上最大的沙漠位于哪个大洲的哪个国家？", "type": ReasoningType.MULTI_HOP, "context": "地理知识"},
            {"question": "发明电话的人是哪个国家的，他还发明了什么重要设备？", "type": ReasoningType.MULTI_HOP, "context": "科技历史"},
            {"question": "获得诺贝尔文学奖最多的国家的首都是什么？", "type": ReasoningType.MULTI_HOP, "context": "文学地理"},
            {"question": "太阳系中距离地球最近的行星的表面温度大约是多少？", "type": ReasoningType.MULTI_HOP, "context": "天文科学"},
            {"question": "中国古代四大发明中最晚发明的那个对哪个朝代的发展影响最大？", "type": ReasoningType.MULTI_HOP, "context": "历史科技"},
            {"question": "写出《百年孤独》的作者来自哪个大洲的哪个国家？", "type": ReasoningType.MULTI_HOP, "context": "文学地理"},
            {"question": "举办过夏季奥运会次数最多的城市位于哪个国家的哪个州？", "type": ReasoningType.MULTI_HOP, "context": "体育地理"},
            {"question": "世界上第一台计算机是在哪个大学诞生的，这所大学位于哪个州？", "type": ReasoningType.MULTI_HOP, "context": "科技教育"},
            {"question": "莎士比亚出生的城市现在属于英国的哪个郡，这个郡的面积大约是多少？", "type": ReasoningType.MULTI_HOP, "context": "文学地理"},
            {"question": "提出进化论的科学家乘坐的那艘著名船只的名字是什么，这次航行持续了多长时间？", "type": ReasoningType.MULTI_HOP, "context": "科学历史"},
            {"question": "世界上最高的瀑布位于哪个国家，这个国家的官方语言是什么？", "type": ReasoningType.MULTI_HOP, "context": "地理语言"},
            {"question": "发现DNA双螺旋结构的科学家中，获得诺贝尔奖的是哪几位，他们获奖时间是哪一年？", "type": ReasoningType.MULTI_HOP, "context": "科学成就"},
            {"question": "制作第一部动画长片的公司创始人出生在哪个国家的哪个州？", "type": ReasoningType.MULTI_HOP, "context": "娱乐历史"},
            {"question": "世界上最深的海沟位于哪个大洋的哪个区域，它的最深处大约有多深？", "type": ReasoningType.MULTI_HOP, "context": "海洋地理"},
            {"question": "发明青霉素的科学家出生在哪个国家，青霉素首次大规模生产是在哪个历史事件期间？", "type": ReasoningType.MULTI_HOP, "context": "医学历史"}
        ]
        
        # 歧义澄清问题
        ambiguity_questions = [
            {"question": "他什么时候出生的？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "代词指代模糊"},
            {"question": "那家餐厅怎么样？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "指代对象不明"},
            {"question": "你能帮我完成这个吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "任务内容模糊"},
            {"question": "这个价格合理吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "对象和标准不明"},
            {"question": "上次说的那个地方在哪里？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "缺乏上下文"},
            {"question": "它什么时候开始的？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "事件主体不明"},
            {"question": "这样做对吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "行为和标准模糊"},
            {"question": "她现在在哪里工作？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "人物指代不明"},
            {"question": "那个方案可行吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "方案内容不明"},
            {"question": "你觉得怎么样？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "评价对象模糊"},
            {"question": "什么时候截止？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "活动主体不明"},
            {"question": "这个效果好吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "产品和标准不明"},
            {"question": "下次我们去哪里？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "活动背景不明"},
            {"question": "他们什么时候回来？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "人群指代模糊"},
            {"question": "这个结果对吗？", "type": ReasoningType.AMBIGUITY_CLARIFICATION, "context": "结果内容和标准不明"}
        ]
        
        all_questions = math_questions + multi_hop_questions + ambiguity_questions
        
        # 为每个问题添加ID
        for i, question in enumerate(all_questions):
            question["id"] = f"phase1_{question['type'].value}_{i+1:03d}"
        
        self.logger.info(f"创建了{len(all_questions)}个第一阶段验证问题")
        return all_questions
    
    def generate_single_dialogue(self, question_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成单个对话"""
        question_id = question_data["id"]
        question_text = question_data["question"]
        reasoning_type = question_data["type"]
        context = question_data.get("context", "")
        
        try:
            self.logger.info(f"生成对话: {question_id}")
            
            # 生成prompt
            if reasoning_type == ReasoningType.MATH_REASONING:
                prompt = self.prompt_generator.generate_math_reasoning_prompt(question_text, context)
            elif reasoning_type == ReasoningType.MULTI_HOP:
                prompt = self.prompt_generator.generate_multi_hop_prompt(question_text, context)
            elif reasoning_type == ReasoningType.AMBIGUITY_CLARIFICATION:
                prompt = self.prompt_generator.generate_ambiguity_clarification_prompt(question_text, context)
            else:
                raise ValueError(f"不支持的推理类型: {reasoning_type}")
            
            # 调用Gemini生成对话
            response = self.gemini_generator._make_request(prompt)
            
            if not response:
                self.logger.error(f"Gemini API返回为空: {question_id}")
                return None
            
            # 尝试解析JSON响应
            try:
                # 提取JSON部分
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    dialogue_data = json.loads(json_str)
                else:
                    raise ValueError("未找到有效的JSON格式")
                
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"JSON解析失败: {question_id}, 错误: {e}")
                # 创建简化的对话结构
                dialogue_data = self._create_fallback_dialogue(question_data, response)
            
            # 添加元数据
            dialogue_data.update({
                "id": question_id,
                "source_question": question_data,
                "generation_timestamp": datetime.now().isoformat(),
                "generator_version": "phase1_v1.0"
            })
            
            # 立即进行质量评分
            quality_type_map = {
                ReasoningType.MATH_REASONING: QuestionType.MATH_REASONING,
                ReasoningType.MULTI_HOP: QuestionType.MULTI_HOP,
                ReasoningType.AMBIGUITY_CLARIFICATION: QuestionType.AMBIGUITY_CLARIFICATION
            }
            
            quality_result = self.quality_scorer.score_dialogue(
                dialogue_data, 
                quality_type_map[reasoning_type]
            )
            
            dialogue_data["quality_score"] = quality_result
            
            # 更新统计
            self._update_stats(reasoning_type.value, True, quality_result["grade"])
            
            self.logger.info(f"成功生成对话: {question_id}, 质量等级: {quality_result['grade']}")
            return dialogue_data
            
        except Exception as e:
            self.logger.error(f"生成对话失败: {question_id}, 错误: {e}")
            self._update_stats(reasoning_type.value, False)
            return None
    
    def _create_fallback_dialogue(self, question_data: Dict[str, Any], raw_response: str) -> Dict[str, Any]:
        """创建备用的对话结构"""
        reasoning_type = question_data["type"]
        original_question = question_data["question"]
        
        # 简化的对话结构
        dialogue = {
            "dialogue_type": reasoning_type.value,
            "original_question": original_question,
            "reconstructed_question": original_question,  # 使用原问题
            "turns": [
                {"role": "user", "content": original_question},
                {"role": "assistant", "content": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response}
            ],
            "generation_note": "fallback_structure_due_to_json_parse_error"
        }
        
        return dialogue
    
    def _update_stats(self, reasoning_type: str, success: bool, quality_grade: str = None):
        """更新生成统计"""
        self.generation_stats["total_attempted"] += 1
        self.generation_stats["by_type"][reasoning_type]["attempted"] += 1
        
        if success:
            self.generation_stats["total_successful"] += 1
            self.generation_stats["by_type"][reasoning_type]["successful"] += 1
            
            if quality_grade:
                self.generation_stats["quality_distribution"][quality_grade] += 1
        else:
            self.generation_stats["by_type"][reasoning_type]["failed"] += 1
    
    def generate_phase1_dataset(self, max_concurrent: int = 3) -> Dict[str, Any]:
        """生成第一阶段数据集"""
        self.logger.info("开始生成第一阶段数据集")
        self.generation_stats["start_time"] = datetime.now().isoformat()
        
        # 创建问题集
        questions = self.create_phase1_questions()
        
        # 生成对话
        dialogues = []
        failed_questions = []
        
        for question_data in questions:
            dialogue = self.generate_single_dialogue(question_data)
            
            if dialogue:
                dialogues.append(dialogue)
            else:
                failed_questions.append(question_data)
            
            # 避免API限流，添加延迟
            time.sleep(2)
        
        self.generation_stats["end_time"] = datetime.now().isoformat()
        
        # 分析结果
        analysis = self._analyze_generation_results(dialogues, failed_questions)
        
        # 构建最终数据集
        dataset = {
            "version": "phase1_v1.0",
            "generation_timestamp": self.generation_stats["end_time"],
            "total_dialogues": len(dialogues),
            "target_count": len(questions),
            "success_rate": len(dialogues) / len(questions) if questions else 0,
            "dialogues": dialogues,
            "failed_questions": failed_questions,
            "generation_stats": self.generation_stats,
            "quality_analysis": analysis,
            "next_steps": self._generate_next_steps_recommendations(analysis)
        }
        
        self.logger.info(f"第一阶段数据集生成完成: {len(dialogues)}/{len(questions)} 成功")
        return dataset
    
    def _analyze_generation_results(self, dialogues: List[Dict[str, Any]], 
                                   failed_questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析生成结果"""
        analysis = {
            "overall_quality": {},
            "by_type_analysis": {},
            "common_issues": [],
            "quality_trends": {}
        }
        
        if not dialogues:
            return analysis
        
        # 整体质量分析
        grades = [d["quality_score"]["grade"] for d in dialogues if "quality_score" in d]
        total_scores = [d["quality_score"]["total_score"] for d in dialogues if "quality_score" in d]
        
        if grades:
            analysis["overall_quality"] = {
                "grade_distribution": {grade: grades.count(grade) for grade in ["A", "B", "C"]},
                "average_score": sum(total_scores) / len(total_scores) if total_scores else 0,
                "high_quality_rate": grades.count("A") / len(grades),
                "acceptable_rate": (grades.count("A") + grades.count("B")) / len(grades)
            }
        
        # 按类型分析
        for dialogue in dialogues:
            dialogue_type = dialogue.get("dialogue_type", "unknown")
            if dialogue_type not in analysis["by_type_analysis"]:
                analysis["by_type_analysis"][dialogue_type] = {
                    "count": 0,
                    "avg_score": 0,
                    "grade_dist": {"A": 0, "B": 0, "C": 0},
                    "common_strengths": [],
                    "common_weaknesses": []
                }
            
            type_analysis = analysis["by_type_analysis"][dialogue_type]
            type_analysis["count"] += 1
            
            if "quality_score" in dialogue:
                quality_data = dialogue["quality_score"]
                type_analysis["avg_score"] += quality_data["total_score"]
                type_analysis["grade_dist"][quality_data["grade"]] += 1
                
                # 收集优势和劣势
                if "detailed_analysis" in quality_data:
                    detailed = quality_data["detailed_analysis"]
                    type_analysis["common_strengths"].extend(detailed.get("strengths", []))
                    type_analysis["common_weaknesses"].extend(detailed.get("weaknesses", []))
        
        # 计算平均分
        for type_name, type_data in analysis["by_type_analysis"].items():
            if type_data["count"] > 0:
                type_data["avg_score"] /= type_data["count"]
        
        return analysis
    
    def _generate_next_steps_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """生成下一步建议"""
        recommendations = []
        
        overall_quality = analysis.get("overall_quality", {})
        high_quality_rate = overall_quality.get("high_quality_rate", 0)
        
        if high_quality_rate < 0.6:
            recommendations.append("整体质量偏低，建议优化prompt模板，增加更多示例和约束")
        
        if high_quality_rate >= 0.8:
            recommendations.append("质量表现良好，可以开始大规模生成")
        
        # 按类型的建议
        by_type = analysis.get("by_type_analysis", {})
        for type_name, type_data in by_type.items():
            avg_score = type_data.get("avg_score", 0)
            if avg_score < 70:
                recommendations.append(f"{type_name}类型需要重点优化prompt设计")
            elif avg_score >= 85:
                recommendations.append(f"{type_name}类型表现优秀，可作为模板参考")
        
        if not recommendations:
            recommendations.append("继续按当前策略进行大规模生成")
        
        return recommendations
    
    def save_phase1_results(self, dataset: Dict[str, Any], output_dir: str = "phase1_results"):
        """保存第一阶段结果"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存完整数据集
        dataset_file = output_path / f"phase1_dataset_{timestamp}.json"
        with open(dataset_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        
        # 保存质量报告
        quality_report = {
            "generation_stats": dataset["generation_stats"],
            "quality_analysis": dataset["quality_analysis"],
            "next_steps": dataset["next_steps"],
            "summary": {
                "total_generated": dataset["total_dialogues"],
                "success_rate": f"{dataset['success_rate']:.1%}",
                "high_quality_rate": f"{dataset['quality_analysis']['overall_quality'].get('high_quality_rate', 0):.1%}"
            }
        }
        
        report_file = output_path / f"phase1_quality_report_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(quality_report, f, ensure_ascii=False, indent=2)
        
        # 生成Markdown报告
        markdown_report = self._generate_markdown_report(dataset)
        md_file = output_path / f"phase1_report_{timestamp}.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        
        self.logger.info(f"第一阶段结果已保存到: {output_path}")
        return {
            "dataset_file": str(dataset_file),
            "report_file": str(report_file),
            "markdown_file": str(md_file)
        }
    
    def _generate_markdown_report(self, dataset: Dict[str, Any]) -> str:
        """生成Markdown格式的报告"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""# 第一阶段数据生成报告

**生成时间**: {timestamp}  
**数据集版本**: {dataset['version']}

## 📊 总体统计

- **目标数量**: {dataset['target_count']} 个对话
- **成功生成**: {dataset['total_dialogues']} 个对话
- **成功率**: {dataset['success_rate']:.1%}

## 🎯 质量分析

### 整体质量分布
"""
        
        overall_quality = dataset['quality_analysis'].get('overall_quality', {})
        if 'grade_distribution' in overall_quality:
            grade_dist = overall_quality['grade_distribution']
            report += f"""
- **A级 (优秀)**: {grade_dist.get('A', 0)} 个 ({grade_dist.get('A', 0)/max(dataset['total_dialogues'], 1):.1%})
- **B级 (良好)**: {grade_dist.get('B', 0)} 个 ({grade_dist.get('B', 0)/max(dataset['total_dialogues'], 1):.1%})
- **C级 (需改进)**: {grade_dist.get('C', 0)} 个 ({grade_dist.get('C', 0)/max(dataset['total_dialogues'], 1):.1%})

**平均分数**: {overall_quality.get('average_score', 0):.1f}
**高质量率**: {overall_quality.get('high_quality_rate', 0):.1%}
"""
        
        # 按类型分析
        by_type = dataset['quality_analysis'].get('by_type_analysis', {})
        if by_type:
            report += "\n### 分类型分析\n\n"
            for type_name, type_data in by_type.items():
                report += f"""#### {type_name}
- **数量**: {type_data['count']} 个
- **平均分**: {type_data['avg_score']:.1f}
- **等级分布**: A({type_data['grade_dist']['A']}) B({type_data['grade_dist']['B']}) C({type_data['grade_dist']['C']})

"""
        
        # 下一步建议
        next_steps = dataset.get('next_steps', [])
        if next_steps:
            report += "## 🚀 下一步建议\n\n"
            for i, step in enumerate(next_steps, 1):
                report += f"{i}. {step}\n"
        
        return report

def main():
    """主函数"""
    print("第三阶段第一阶段数据生成器")
    print("=" * 50)
    
    # 创建生成器
    generator = Phase1DataGenerator()
    
    # 生成数据集
    print("🔄 开始生成第一阶段验证数据集...")
    dataset = generator.generate_phase1_dataset()
    
    # 保存结果
    print("💾 保存生成结果...")
    file_paths = generator.save_phase1_results(dataset)
    
    # 显示总结
    print(f"\n✅ 第一阶段数据生成完成!")
    print(f"📊 成功率: {dataset['success_rate']:.1%}")
    print(f"📈 高质量率: {dataset['quality_analysis']['overall_quality'].get('high_quality_rate', 0):.1%}")
    print(f"📁 文件保存:")
    for file_type, file_path in file_paths.items():
        print(f"   {file_type}: {file_path}")

if __name__ == "__main__":
    main()
