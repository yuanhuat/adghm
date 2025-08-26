import requests
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from app import db
from app.utils.timezone import beijing_time
from app.models.query_log_analysis import QueryLogAnalysis
from app.models.adguard_config import AdGuardConfig

class AIAnalysisService:
    """AI分析服务类
    
    集成DeepSeek API来分析DNS查询日志，识别广告、恶意软件、追踪器等
    """
    
    def __init__(self):
        """初始化AI分析服务"""
        self.deepseek_api_key = None
        self.deepseek_base_url = "https://api.deepseek.com/v1"
        self.logger = logging.getLogger(__name__)
        
        # 从配置中获取API密钥
        config = AdGuardConfig.get_config()
        if hasattr(config, 'deepseek_api_key'):
            self.deepseek_api_key = config.deepseek_api_key
    
    def set_api_key(self, api_key: str) -> None:
        """设置DeepSeek API密钥
        
        Args:
            api_key: DeepSeek API密钥
        """
        self.deepseek_api_key = api_key
    
    def analyze_domain(self, domain: str) -> Optional[Dict]:
        """分析单个域名
        
        Args:
            domain: 要分析的域名
            
        Returns:
            分析结果字典，包含分类、置信度、描述等信息
        """
        if not self.deepseek_api_key:
            self.logger.warning("DeepSeek API密钥未配置")
            return None
        
        # 检查是否已经分析过该域名（24小时内）
        recent_analysis = QueryLogAnalysis.query.filter(
            QueryLogAnalysis.domain == domain,
            QueryLogAnalysis.analyzed_at > beijing_time() - timedelta(hours=24)
        ).first()
        
        if recent_analysis:
            return recent_analysis.to_dict()
        
        try:
            # 构建分析提示
            prompt = self._build_analysis_prompt(domain)
            
            # 调用DeepSeek API
            response = self._call_deepseek_api(prompt)
            
            if response:
                # 解析AI响应
                analysis_result = self._parse_ai_response(response)
                
                # 保存分析结果到数据库
                if analysis_result:
                    self._save_analysis_result(domain, analysis_result)
                    return analysis_result
            
        except Exception as e:
            self.logger.error(f"分析域名 {domain} 时出错: {str(e)}")
        
        return None
    
    def analyze_domains_batch(self, domains: List[str]) -> Dict[str, Dict]:
        """批量分析域名
        
        Args:
            domains: 域名列表
            
        Returns:
            域名分析结果字典
        """
        results = {}
        
        for domain in domains:
            try:
                result = self.analyze_domain(domain)
                if result:
                    results[domain] = result
            except Exception as e:
                self.logger.error(f"批量分析域名 {domain} 时出错: {str(e)}")
                continue
        
        return results
    
    def get_pending_reviews(self) -> List[QueryLogAnalysis]:
        """获取待审核的分析结果
        
        Returns:
            待审核的分析结果列表
        """
        return QueryLogAnalysis.query.filter(
            QueryLogAnalysis.is_reviewed == False,
            QueryLogAnalysis.recommendation.in_(['block', 'monitor'])
        ).order_by(QueryLogAnalysis.confidence.desc()).all()
    
    def review_analysis(self, analysis_id: int, admin_action: str, 
                       admin_notes: str = None, reviewer_id: int = None) -> bool:
        """管理员审核分析结果
        
        Args:
            analysis_id: 分析结果ID
            admin_action: 管理员采取的行动 (block, allow, ignore)
            admin_notes: 管理员备注
            reviewer_id: 审核人ID
            
        Returns:
            是否审核成功
        """
        try:
            analysis = QueryLogAnalysis.query.get(analysis_id)
            if not analysis:
                return False
            
            analysis.is_reviewed = True
            analysis.admin_action = admin_action
            analysis.admin_notes = admin_notes
            analysis.reviewed_at = beijing_time()
            analysis.reviewed_by = reviewer_id
            
            db.session.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"审核分析结果时出错: {str(e)}")
            db.session.rollback()
            return False
    
    def _build_analysis_prompt(self, domain: str) -> str:
        """构建AI分析提示
        
        Args:
            domain: 域名
            
        Returns:
            分析提示文本
        """
        prompt = f"""
请分析以下域名是否为广告、追踪器、恶意软件或其他可疑内容：

域名: {domain}

请从以下几个方面进行分析：
1. 域名结构和命名模式
2. 已知的广告网络和追踪器数据库
3. 恶意软件和钓鱼网站特征
4. 域名的商业用途和合法性

请以JSON格式返回分析结果，包含以下字段：
{{
    "analysis_type": "ad/tracker/malware/legitimate",
    "confidence": 0.0-1.0,
    "category": "具体分类（如：广告网络、社交媒体追踪器、恶意软件C&C等）",
    "description": "详细分析说明",
    "recommendation": "block/allow/monitor"
}}

注意：
- confidence表示置信度，0.8以上为高置信度
- 对于不确定的域名，建议使用monitor
- 只有明确的广告、追踪器或恶意内容才建议block
"""
        return prompt
    
    def _call_deepseek_api(self, prompt: str) -> Optional[str]:
        """调用DeepSeek API
        
        Args:
            prompt: 分析提示
            
        Returns:
            API响应内容
        """
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个网络安全专家，专门分析DNS查询日志中的域名，识别广告、追踪器、恶意软件等威胁。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                f"{self.deepseek_base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                self.logger.error(f"DeepSeek API调用失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"调用DeepSeek API时出错: {str(e)}")
            return None
    
    def _parse_ai_response(self, response: str) -> Optional[Dict]:
        """解析AI响应
        
        Args:
            response: AI响应文本
            
        Returns:
            解析后的分析结果
        """
        try:
            # 尝试从响应中提取JSON
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                result = json.loads(json_str)
                
                # 验证必需字段
                required_fields = ['analysis_type', 'confidence', 'recommendation']
                if all(field in result for field in required_fields):
                    return result
            
            self.logger.warning(f"无法解析AI响应: {response}")
            return None
            
        except json.JSONDecodeError as e:
            self.logger.error(f"解析AI响应JSON时出错: {str(e)}")
            return None
    
    def _save_analysis_result(self, domain: str, analysis_result: Dict) -> None:
        """保存分析结果到数据库
        
        Args:
            domain: 域名
            analysis_result: 分析结果
        """
        try:
            analysis = QueryLogAnalysis(
                domain=domain,
                analysis_type=analysis_result.get('analysis_type', 'unknown'),
                confidence=float(analysis_result.get('confidence', 0.0)),
                category=analysis_result.get('category'),
                description=analysis_result.get('description'),
                recommendation=analysis_result.get('recommendation', 'monitor'),
                ai_model='deepseek'
            )
            
            db.session.add(analysis)
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"保存分析结果时出错: {str(e)}")
            db.session.rollback()
    
    def get_analysis_stats(self) -> Dict:
        """获取分析统计信息
        
        Returns:
            统计信息字典
        """
        try:
            total_analyzed = QueryLogAnalysis.query.count()
            pending_reviews = QueryLogAnalysis.query.filter(
                QueryLogAnalysis.is_reviewed == False
            ).count()
            
            # 按分析类型统计
            type_stats = db.session.query(
                QueryLogAnalysis.analysis_type,
                db.func.count(QueryLogAnalysis.id)
            ).group_by(QueryLogAnalysis.analysis_type).all()
            
            # 按推荐操作统计
            recommendation_stats = db.session.query(
                QueryLogAnalysis.recommendation,
                db.func.count(QueryLogAnalysis.id)
            ).group_by(QueryLogAnalysis.recommendation).all()
            
            return {
                'total_analyzed': total_analyzed,
                'pending_reviews': pending_reviews,
                'type_distribution': dict(type_stats),
                'recommendation_distribution': dict(recommendation_stats)
            }
            
        except Exception as e:
            self.logger.error(f"获取分析统计信息时出错: {str(e)}")
            return {}