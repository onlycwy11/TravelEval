from .base import BaseStrategy
from typing import Set, Dict
from agent.schemas.travel_plan import FinalTravelPlan


class ReActReflexionStrategy(BaseStrategy):
    """ReAct & Reflexion 策略"""

    def __init__(self, max_reflections: int = 3):
        super().__init__("ReAct&Reflexion")
        self.max_reflections = max_reflections

    def get_system_prompt(self, station_constraints: Set) -> str:
        return f"""你是一名专业的旅行规划师，拥有完整的目标城市 POI 数据库。

# 重要指令
1. 使用标准POI名称，如：故宫博物院、上海迪士尼度假区
2. 严格遵循以下多轮交互格式（至多{self.max_reflections}轮）
    - Thought: 分析当前规划状态，明确下一步需要解决的具体问题（如"需确定首日住宿地点"）。
    - Action: 规划下一步所需的关键数据或决策，例如："从数据库中选择一个符合亲子需求的酒店"或"计算当前总花费"。
    - Observation: 基于常识与推理，给出该步骤的解决方案或数据估算，作为后续决策依据。
3. 当所有核心问题（行程、住宿、交通、预算）均已解决时，请输出最终规划。

本次规划中城际交通必须使用以下指定站点：
{station_constraints}

【JSON Schema】
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# 嵌套结构定义（使用 Pydantic 库来实现结构化输出）
class RoomTypeDetail(BaseModel):
    type: Literal["单人房", "大床房", "双人房", "家庭房"] = Field(..., description="房型")
    quantity: int = Field(..., description="房间数量")
    price_per_night: float = Field(..., description="每晚单价")
    nights: int = Field(..., description="入住晚数")

class Accommodation(BaseModel):
    hotel_name: str = Field(..., description="酒店名称")
    room_type: List[RoomTypeDetail] = Field(..., description="房型列表")
    total_cost: float = Field(..., description="住宿总费用")

class TransportDetails(BaseModel):
    transport_number: str = Field(..., description="车次/航班号")
    price: float = Field(..., description="票价")
    number: int = Field(..., description="数量")

class TransportType(BaseModel):
    description: str = Field(..., description="行程描述")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="出发时间，格式 HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="到达时间，格式 HH:MM")
    location_name: str = Field(..., description="目的地站点")
    cost: float = Field(..., description="行程费用")
    transportation_to: Literal["高铁", "飞机", "动车", "快速", "特快", "直达特快"] = Field(..., description="交通工具类型")
    transportation_cost: float = Field(..., description="交通费用")
    details: TransportDetails = Field(..., description="交通工具的详细信息，例如车次/航班号、票价、数量等")

class IntercityTransportation(BaseModel):
    transport_type: List[TransportType] = Field(..., description="城际交通类型列表")
    total_cost: float = Field(..., description="城际交通总费用")

class ActivityTransportDetails(BaseModel):
    transport_time: str = Field(..., description="交通预计时间（如 '30' 表示30分钟）")
    ticket_type: Optional[str] = Field(None, description="票务类型（如观光票、一日票等，仅景点时填写）")
    ticket_price: Optional[float] = Field(None, description="票务单价（仅景点时填写）")
    ticket_number: Optional[int] = Field(None, description="票务数量（仅景点时填写）")
    cuisine: Optional[str] = Field(None, description="推荐菜品（仅餐饮时填写）")
    line: Optional[str] = Field(None, description="地铁线路（仅地铁时填写）")
    bus_number: Optional[str] = Field(None, description="公交车号（仅公交时填写）")
    load_limit: Optional[int] = Field(None, description="限载人数（仅打车或包车时填写）")
    car_number: Optional[int] = Field(None, description="车辆数（仅打车或包车时填写）")

class DailyActivity(BaseModel):
    type: Literal["intercity_transport", "attraction", "meal", "accommodation", "accommodation_check_in", "accommodation_check_out"] = Field(..., description="活动类型")
    description: str = Field(..., description="活动描述")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="开始时间，格式 HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="结束时间，格式 HH:MM")
    location_name: str = Field(..., description="地点名称")
    cost: float = Field(..., description="活动费用（仅 POI 本身的费用，不包括交通费用）")
    transportation_to: Literal["步行", "骑行", "驾车", "公交", "地铁", "打车", "包车"] = Field(..., description="交通方式")
    transportation_cost: float = Field(..., description="交通费用")
    details: ActivityTransportDetails = Field(..., description="根据类型填充详细信息")

class DailyEndingPoint(BaseModel):
    type: Literal["intercity_transport", "accommodation"] = Field(..., description="终点类型")
    description: str = Field(..., description="今日终点描述")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="出发时间，格式 HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="到达时间，格式 HH:MM")
    location_name: str = Field(..., description="终点名称（车站或酒店）")
    cost: float = Field(..., description="费用")
    transportation_to: Literal["步行", "骑行", "驾车", "公交", "地铁", "打车", "包车"] = Field(..., description="交通方式")
    transportation_cost: float = Field(..., description="交通费用")
    details: ActivityTransportDetails = Field(..., description="交通详情")

class DailyPlan(BaseModel):
    day: int = Field(..., description="第几天")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="日期，格式 YYYY-MM-DD")
    starting_point: str = Field(..., description="起点")
    ending_point: DailyEndingPoint = Field(..., description="终点")
    activities: List[DailyActivity] = Field(..., description="每日活动列表(不包含城际交通)")

class CostBreakdown(BaseModel):
    attractions: float = Field(..., description="景点总花费")
    intercity_transportation: float = Field(..., description="城际交通总花费")
    intracity_transportation: float = Field(..., description="市内交通总花费")
    accommodation: float = Field(..., description="住宿总花费")
    meals: float = Field(..., description="餐饮总花费")
    other: float = Field(..., description="其他花费")
    total: float = Field(..., description="总计")

class Summary(BaseModel):
    total_days: int = Field(..., description="总天数")
    total_travelers: int = Field(..., description="总人数")
    departure: str = Field(..., description="旅行出发城市")
    destination: str = Field(..., description="旅行目的城市")
    total_budget: float = Field(..., description="总预算")
    calculated_total_cost: float = Field(..., description="计算总花费")
    is_within_budget: bool = Field(..., description="是否在预算内")

class ItineraryContent(BaseModel):
    summary: Summary
    accommodation: Accommodation
    intercity_transport: IntercityTransportation
    daily_plans: List[DailyPlan]
    cost_breakdown: CostBreakdown

class FinalTravelPlan(BaseModel):
    query_uid: str = Field(..., description="对应用户提问唯一ID，例如：Txxxx 或 Gxx-x")
    itinerary: ItineraryContent = Field(..., description="行程详情")"""

    def get_user_prompt(self, user_query: Dict) -> str:
        return f"用户请求：{user_query}\n请开始你的 ReAct 循环，最后输出严格符合格式的 JSON。"

    def get_reflexion_prompt(self, response: Dict) -> str:
        return f"""你是一名旅行规划评估专家，需对以下规划方案进行批判性反思。请严格按照原JSON结构输出：

# 输入数据
{response}

# 反思框架
1. 当前方案优势
   - 示例："住宿集中在地铁2号线沿线，交通便利"
   - 示例："核心景点覆盖率高，无重复路线"
2. 已识别问题或潜在风险
   - 预算类："第三日餐饮预算超支15%"
   - 时间类："迪士尼乐园与机场返程时间间隔仅2小时，存在误机风险"
   - 体验类："亲子行程中缺乏室内活动备选"
3. 优化优先级
   - 必须排序："1. 调整迪士尼返程交通 → 2. 压缩餐饮预算 → 3. 增加室内活动备选方案"

# 输出要求
生成反思结果后，再严格遵循格式输出JSON规划方案。

【JSON Schema】
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
# 嵌套结构定义（使用 Pydantic 库来实现结构化输出）
class RoomTypeDetail(BaseModel):
    type: Literal["单人房", "大床房", "双人房", "家庭房"] = Field(..., description="房型")
    quantity: int = Field(..., description="房间数量")
    price_per_night: float = Field(..., description="每晚单价")
    nights: int = Field(..., description="入住晚数")

class Accommodation(BaseModel):
    hotel_name: str = Field(..., description="酒店名称")
    room_type: List[RoomTypeDetail] = Field(..., description="房型列表")
    total_cost: float = Field(..., description="住宿总费用")

class TransportDetails(BaseModel):
    transport_number: str = Field(..., description="车次/航班号")
    price: float = Field(..., description="票价")
    number: int = Field(..., description="数量")

class TransportType(BaseModel):
    description: str = Field(..., description="行程描述")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="出发时间，格式 HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="到达时间，格式 HH:MM")
    location_name: str = Field(..., description="目的地站点")
    cost: float = Field(..., description="行程费用")
    transportation_to: Literal["高铁", "飞机", "动车", "快速", "特快", "直达特快"] = Field(..., description="交通工具类型")
    transportation_cost: float = Field(..., description="交通费用")
    details: TransportDetails = Field(..., description="交通工具的详细信息，例如车次/航班号、票价、数量等")

class IntercityTransportation(BaseModel):
    transport_type: List[TransportType] = Field(..., description="城际交通类型列表")
    total_cost: float = Field(..., description="城际交通总费用")

class ActivityTransportDetails(BaseModel):
    transport_time: str = Field(..., description="交通预计时间（如 '30' 表示30分钟）")
    ticket_type: Optional[str] = Field(None, description="票务类型（如观光票、一日票等，仅景点时填写）")
    ticket_price: Optional[float] = Field(None, description="票务单价（仅景点时填写）")
    ticket_number: Optional[int] = Field(None, description="票务数量（仅景点时填写）")
    cuisine: Optional[str] = Field(None, description="推荐菜品（仅餐饮时填写）")
    line: Optional[str] = Field(None, description="地铁线路（仅地铁时填写）")
    bus_number: Optional[str] = Field(None, description="公交车号（仅公交时填写）")
    load_limit: Optional[int] = Field(None, description="限载人数（仅打车或包车时填写）")
    car_number: Optional[int] = Field(None, description="车辆数（仅打车或包车时填写）")

class DailyActivity(BaseModel):
    type: Literal["intercity_transport", "attraction", "meal", "accommodation", "accommodation_check_in", "accommodation_check_out"] = Field(..., description="活动类型")
    description: str = Field(..., description="活动描述")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="开始时间，格式 HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="结束时间，格式 HH:MM")
    location_name: str = Field(..., description="地点名称")
    cost: float = Field(..., description="活动费用（仅 POI 本身的费用，不包括交通费用）")
    transportation_to: Literal["步行", "骑行", "驾车", "公交", "地铁", "打车", "包车"] = Field(..., description="交通方式")
    transportation_cost: float = Field(..., description="交通费用")
    details: ActivityTransportDetails = Field(..., description="根据类型填充详细信息")

class DailyEndingPoint(BaseModel):
    type: Literal["intercity_transport", "accommodation"] = Field(..., description="终点类型")
    description: str = Field(..., description="今日终点描述")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="出发时间，格式 HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="到达时间，格式 HH:MM")
    location_name: str = Field(..., description="终点名称（车站或酒店）")
    cost: float = Field(..., description="费用")
    transportation_to: Literal["步行", "骑行", "驾车", "公交", "地铁", "打车", "包车"] = Field(..., description="交通方式")
    transportation_cost: float = Field(..., description="交通费用")
    details: ActivityTransportDetails = Field(..., description="交通详情")

class DailyPlan(BaseModel):
    day: int = Field(..., description="第几天")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="日期，格式 YYYY-MM-DD")
    starting_point: str = Field(..., description="起点")
    ending_point: DailyEndingPoint = Field(..., description="终点")
    activities: List[DailyActivity] = Field(..., description="每日活动列表(不包含城际交通)")

class CostBreakdown(BaseModel):
    attractions: float = Field(..., description="景点总花费")
    intercity_transportation: float = Field(..., description="城际交通总花费")
    intracity_transportation: float = Field(..., description="市内交通总花费")
    accommodation: float = Field(..., description="住宿总花费")
    meals: float = Field(..., description="餐饮总花费")
    other: float = Field(..., description="其他花费")
    total: float = Field(..., description="总计")

class Summary(BaseModel):
    total_days: int = Field(..., description="总天数")
    total_travelers: int = Field(..., description="总人数")
    departure: str = Field(..., description="旅行出发城市")
    destination: str = Field(..., description="旅行目的城市")
    total_budget: float = Field(..., description="总预算")
    calculated_total_cost: float = Field(..., description="计算总花费")
    is_within_budget: bool = Field(..., description="是否在预算内")

class ItineraryContent(BaseModel):
    summary: Summary
    accommodation: Accommodation
    intercity_transport: IntercityTransportation
    daily_plans: List[DailyPlan]
    cost_breakdown: CostBreakdown

class FinalTravelPlan(BaseModel):
    query_uid: str = Field(..., description="对应用户提问唯一ID，例如：Txxxx 或 Gxx-x")
    itinerary: ItineraryContent = Field(..., description="行程详情")"""