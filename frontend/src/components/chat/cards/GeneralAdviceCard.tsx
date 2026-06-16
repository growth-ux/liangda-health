import type { GeneralAdvicePayload } from '../../../schemas/agentResponse';

type Props = { payload: GeneralAdvicePayload };

export function GeneralAdviceCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="font-semibold text-stone-700">💡 {payload.topic}</div>
      <div className="rounded-lg bg-white p-3 text-stone-700 leading-relaxed">{payload.advice}</div>
      {payload.cautions.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3">
          <div className="text-xs font-semibold text-amber-800 mb-1.5">⚠️ 注意</div>
          <ul className="list-disc pl-5 text-amber-900 space-y-0.5">
            {payload.cautions.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
