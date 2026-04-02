import instructor
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

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
    transportation_to: Literal["走路", "步行", "骑行", "驾车", "公交", "地铁", "打车", "包车", "高铁", "飞机"] = Field(..., description="交通方式")
    transportation_cost: float = Field(..., description="交通费用")
    details: Dict[str, Any] = Field(..., description="根据类型填充详细信息")

class DailyEndingPoint(BaseModel):
    type: Literal["intercity_transport", "accommodation_check_in", "accommodation"] = Field(..., description="终点类型")
    description: str = Field(..., description="今日终点描述")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="出发时间，格式 HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$", description="到达时间，格式 HH:MM")
    location_name: str = Field(..., description="终点名称（车站或酒店）")
    cost: float = Field(..., description="费用")
    transportation_to: Literal["走路", "步行", "骑行", "驾车", "公交", "地铁", "打车", "包车", "高铁", "飞机"] = Field(..., description="交通方式")
    transportation_cost: float = Field(..., description="交通费用")
    details: Dict[str, Any] = Field(..., description="交通详情")

class DailyPlan(BaseModel):
    day: int = Field(..., description="第几天")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="日期，格式 YYYY-MM-DD")
    starting_point: str = Field(..., description="起点")
    ending_point: DailyEndingPoint = Field(..., description="终点")
    activities: List[DailyActivity] = Field(..., description="每日活动列表")

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
    itinerary: ItineraryContent = Field(..., description="行程详情")

if __name__ == "__main__":
    client = instructor.from_provider("openai/deepseek", api_key="sk-d658bd05649148499ad2aeeeba1c1c07")
    user = client.chat.completions.create(
        response_model=FinalTravelPlan,
        messages=[{"role": "user", "content": "我和朋友两人要从北京到杭州玩3天，预算4000。"}]
    )

    print(user)