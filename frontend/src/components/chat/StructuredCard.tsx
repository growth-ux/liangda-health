import type { StructuredCard as Card } from '../../schemas/agentResponse';
import { MealPlanCard } from './cards/MealPlanCard';
import { QaCard } from './cards/QaCard';
import { GreetingCard } from './cards/GreetingCard';
import { KbInterpretationCard } from './cards/KbInterpretationCard';
import { GeneralAdviceCard } from './cards/GeneralAdviceCard';

type Props = { card: Card };

export function StructuredCard({ card }: Props) {
  switch (card.kind) {
    case 'meal_plan':
      return <MealPlanCard payload={card.payload as any} />;
    case 'qa':
      return <QaCard payload={card.payload as any} />;
    case 'greeting':
      return <GreetingCard payload={card.payload as any} />;
    case 'kb_interpretation':
      return <KbInterpretationCard payload={card.payload as any} />;
    case 'general_advice':
      return <GeneralAdviceCard payload={card.payload as any} />;
    default: {
      // 未知 kind（理论上 Pydantic 不会放过，但前端兜底）
      const exhaustive: never = card.kind;
      return <pre className="text-xs text-red-500">{JSON.stringify(exhaustive)}</pre>;
    }
  }
}
