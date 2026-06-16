import type { QaPayload } from '../../../schemas/agentResponse';

type Props = { payload: QaPayload };

export function QaCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="font-semibold text-stone-700">💬 {payload.question_topic}</div>
      <div className="rounded-lg bg-white p-3 text-stone-700 leading-relaxed">{payload.answer}</div>
      {payload.tips.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="text-xs font-semibold text-emerald-700 mb-1.5">小贴士</div>
          <ul className="list-disc pl-5 text-stone-700 space-y-0.5">
            {payload.tips.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
