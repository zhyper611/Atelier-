import type { TaskPlan } from "../api/types";

type PlanPanelProps = {
  plan: TaskPlan | null;
};

export function PlanPanel({ plan }: PlanPanelProps) {
  if (!plan) {
    return null;
  }

  return (
    <section className="plan-panel" aria-label="任务计划">
      <header className="plan-panel__header">
        <p className="plan-panel__eyebrow">Task Plan</p>
        <h2>执行计划</h2>
      </header>
      <p className="plan-panel__goal">{plan.goal}</p>
      <ol className="plan-panel__steps">
        {plan.steps.map((step) => (
          <li
            key={step.id}
            className={`plan-panel__step plan-panel__step--${step.status}`}
          >
            <span className="plan-panel__step-title">{step.title}</span>
            {step.description ? (
              <span className="plan-panel__step-desc">{step.description}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
