import type { GreetingPayload } from '../../../schemas/agentResponse';

type Props = { payload: GreetingPayload };

export function GreetingCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="rounded-lg bg-white p-3 text-stone-700 leading-relaxed">{payload.message}</div>
      {payload.suggested_topics.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="text-xs font-semibold text-emerald-700 mb-1.5">你可以问我</div>
          <div className="flex flex-wrap gap-1.5">
            {payload.suggested_topics.map((t, i) => (
              <span key={i} className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs text-emerald-700">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
