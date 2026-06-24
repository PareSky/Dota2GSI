# 检索块索引 / Retrieval Block Index

## 中文说明

总块数: 678

### 块类型分布
- effect_lookup: 64
- hero_item_need: 118
- hero_profile: 127
- item_hero_counter: 52
- item_profile: 190
- skill_upgrade: 127

### 块类型说明
- hero_profile: 英雄画像块，含特征、物品需求、克制关系、升级摘要
- item_profile: 物品画像块，含特征、效果、保护对象、克制对象
- hero_item_need: 英雄物品依赖块，按英雄聚合所有依赖物品
- item_hero_counter: 物品英雄克制块，按物品聚合所有克制英雄
- skill_upgrade: 技能升级评估块，包含神杖与魔晶的价值和详情
- effect_lookup: 效果时长速查块，按效果标签聚合相关技能与物品

## English

Total blocks: 678

### Block Type Distribution
- effect_lookup: 64
- hero_item_need: 118
- hero_profile: 127
- item_hero_counter: 52
- item_profile: 190
- skill_upgrade: 127

### Block Type Notes
- hero_profile: hero profile blocks with traits, item needs, counters, and upgrade summaries
- item_profile: item profile blocks with traits, effects, protected targets, and counter targets
- hero_item_need: hero-to-item dependency blocks aggregated by hero
- item_hero_counter: item-to-hero counter blocks aggregated by item
- skill_upgrade: skill upgrade evaluation blocks for Aghanim's Scepter and Shard value/details
- effect_lookup: quick lookup blocks for effect duration, aggregated by effect tag across skills and items
