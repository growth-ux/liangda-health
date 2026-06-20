import type { KbInterpretationPayload } from '../../../schemas/agentResponse';

type Props = { payload: KbInterpretationPayload };

export function KbInterpretationCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="flex items-center gap-2 text-stone-600">
        <span>📋</span>
        <span className="font-semibold">关于「{payload.topic}」的解读</span>
      </div>

      <div className="rounded-lg bg-white p-3">
        <div className="text-xs font-semibold text-emerald-700 mb-1.5">报告依据</div>
        <ul className="space-y-1.5 text-stone-700">
          {payload.evidence.map((e, i) => (
            <li key={i} className="leading-relaxed">
              <span className="text-stone-500 text-xs">[{e.source_label}]</span> {e.excerpt}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg bg-white p-3">
        <div className="text-xs font-semibold text-emerald-700 mb-1.5">一般建议</div>
        <ul className="space-y-1 text-stone-700">
          {payload.suggestions.map((s, i) => (
            <li key={i} className="leading-relaxed">
              {s.priority === 'primary' && <span className="text-emerald-600 mr-1">●</span>}
              {s.priority === 'secondary' && <span className="text-stone-400 mr-1">○</span>}
              {s.text}
            </li>
          ))}
        </ul>
      </div>

      {payload.red_flags.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3">
          <div className="text-xs font-semibold text-amber-800 mb-1.5">⚠️ 需要就医的信号</div>
          <ul className="list-disc pl-5 text-amber-900 space-y-0.5">
            {payload.red_flags.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
