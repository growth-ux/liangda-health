import type { MealItem, MealPlanPayload, MemberAdjustment } from '../../../schemas/agentResponse';

type Props = { payload: MealPlanPayload };

const SLOT_LABEL: Record<NonNullable<MealItem['slot']>, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
};

const SLOT_COLOR: Record<NonNullable<MealItem['slot']>, string> = {
  breakfast: 'border-amber-300',
  lunch: 'border-emerald-400',
  dinner: 'border-violet-400',
};

const SLOT_TITLE: Record<NonNullable<MealItem['slot']>, string> = {
  breakfast: 'text-amber-700',
  lunch: 'text-emerald-700',
  dinner: 'text-violet-700',
};

export function MealPlanCard({ payload }: Props) {
  const { scope, target_member_name, meal_items, member_adjustments, avoid_tags, extra_note } = payload;

  // 按 slot 分组
  const bySlot: Record<NonNullable<MealItem['slot']>, MealItem[]> = {
    breakfast: [], lunch: [], dinner: [],
  };
  for (const item of meal_items) {
    if (item.slot) bySlot[item.slot].push(item);
  }

  return (
    <div className="mt-3 flex flex-col gap-3 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="flex items-center gap-2 text-stone-600">
        <span className="text-base">🍽️</span>
        <span className="font-semibold">
          {scope === 'family' ? '全家' : target_member_name || '单人'} · 餐单
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {(['breakfast', 'lunch', 'dinner'] as const).map((slot) => {
          const items = bySlot[slot];
          if (items.length === 0) return null;
          return (
            <div key={slot} className={`rounded-lg border-t-4 ${SLOT_COLOR[slot]} bg-white p-3`}>
              <div className={`text-xs font-semibold ${SLOT_TITLE[slot]} mb-1.5`}>{SLOT_LABEL[slot]}</div>
              {items.map((item, i) => (
                <div key={i} className="text-stone-700 leading-relaxed">
                  {item.title}
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {member_adjustments.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="text-xs font-semibold text-emerald-700 mb-2">👨‍👩‍👧 成员调整</div>
          <div className="flex flex-wrap gap-1.5">
            {member_adjustments.map((adj: MemberAdjustment, i) => (
              <span key={i} className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs text-emerald-700">
                {adj.member_name}: {adj.note}
              </span>
            ))}
          </div>
        </div>
      )}

      {avoid_tags.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3">
          <div className="text-xs font-semibold text-amber-800 mb-2">⚠️ 避免</div>
          <div className="flex flex-wrap gap-1.5">
            {avoid_tags.map((tag, i) => (
              <span key={i} className="rounded-full bg-white px-2.5 py-0.5 text-xs text-amber-800">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {extra_note && (
        <div className="text-xs text-stone-500 px-1">💡 {extra_note}</div>
      )}
    </div>
  );
}
