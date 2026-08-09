import pathlib

f = pathlib.Path('backend/app/services/meal_product_recommendation_service.py')
content = f.read_text()

old = '''        # SQLite 中 IN 子句无法匹配 NULL，需要用 is_(None) 单独处理
        member_filter = MallProductFeedback.member_id.in_(member_ids) if member_ids else None
        null_filter = MallProductFeedback.member_id.is_(None)
        combined_filter = or_(member_filter, null_filter) if member_filter else null_filter'''

new = '''        # SQLite 中 IN 子句无法匹配 NULL，需要用 is_(None) 单独处理
        null_filter = MallProductFeedback.member_id.is_(None)
        if member_ids:
            combined_filter = or_(MallProductFeedback.member_id.in_(member_ids), null_filter)
        else:
            combined_filter = null_filter'''

if old in content:
    content = content.replace(old, new)
    f.write_text(content)
    print('REPLACED')
else:
    print('NOT FOUND')
