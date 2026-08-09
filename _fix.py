import pathlib

f = pathlib.Path('backend/app/services/meal_product_recommendation_service.py')
content = f.read_text()

old = '        _PENALTY = {"dislike": -100, "too_expensive": -50, "like": 30, "purchased": -20}\n        rows = (\n            self.db.query(MallProductFeedback)\n            .filter(MallProductFeedback.member_id.in_(member_ids + [None]))\n            .order_by(MallProductFeedback.created_at.desc())\n            .limit(50)\n            .all()\n        )'

new = '        _PENALTY = {"dislike": -100, "too_expensive": -50, "like": 30, "purchased": -20}\n        # SQLite 中 IN 子句无法匹配 NULL，需要用 is_(None) 单独处理\n        member_filter = MallProductFeedback.member_id.in_(member_ids) if member_ids else None\n        null_filter = MallProductFeedback.member_id.is_(None)\n        combined_filter = or_(member_filter, null_filter) if member_filter else null_filter\n        rows = (\n            self.db.query(MallProductFeedback)\n            .filter(combined_filter)\n            .order_by(MallProductFeedback.created_at.desc())\n            .limit(50)\n            .all()\n        )'

if old in content:
    content = content.replace(old, new)
    f.write_text(content)
    print('REPLACED')
else:
    print('NOT FOUND')
