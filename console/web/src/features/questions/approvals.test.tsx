import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Approval, QuestionDetail } from "./api";
import { PlanApprovals } from "./questions";
import { FAKE_DATA } from "./testData";

const HASH = "sha256:" + "a".repeat(64);

function approval(over: Partial<Approval>): Approval {
  return {
    name: "appr-mic-20260925-002-r1.json", agent: "microscope", id: "appr-mic-20260925-002-r1",
    qid: "mic-20260925-002", revision: 1, status: "APPROVED", plan_id: "plan-mic-20260925-002-r1",
    plan_revision: 1, plan_hash: HASH, approved_by: "kyuhwan", approved_at: "2026-09-25T10:00:00Z",
    source: "soft-matter-agents", plan_found: true, data: null, ...over,
  };
}

function detail(over: Partial<QuestionDetail>): QuestionDetail {
  return { ...FAKE_DATA.questions[0], ...over };
}

describe("plan approvals on a question (read only)", () => {
  it("says which plan each approval signs", () => {
    render(
      <PlanApprovals
        detail={detail({
          plan_hash: HASH,
          approvals: [
            approval({}),
            approval({ name: "r2", id: "appr-r2", plan_hash: "sha256:" + "b".repeat(64) }),
            approval({ name: "r3", id: "appr-r3", plan_hash: "sha256:" + "c".repeat(64), plan_found: false }),
          ],
        })}
      />,
    );
    const box = screen.getByRole("region", { name: "Approvals" });
    expect(within(box).getByText(HASH)).toBeTruthy();
    const items = within(box).getAllByRole("listitem").map((li) => li.textContent);
    expect(items[0]).toMatch(/appr-mic-20260925-002-r1 · APPROVED by kyuhwan .* signs this version's plan/);
    expect(items[1]).toMatch(/signs another version's plan/);
    expect(items[2]).toMatch(/signs a plan that is not in the question folder/);
  });

  it("a plan with no approval says so; no plan and no approval shows nothing", () => {
    const { unmount } = render(<PlanApprovals detail={detail({ plan_hash: HASH, approvals: [] })} />);
    expect(screen.getByText("No approval in approvals/ names this question.")).toBeTruthy();
    unmount();
    render(<PlanApprovals detail={detail({ plan_hash: null, approvals: [] })} />);
    expect(screen.queryByRole("region", { name: "Approvals" })).toBeNull();
  });
});
