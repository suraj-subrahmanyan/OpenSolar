function text(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}


function explicitActor(value: unknown): string {
  const role = text(value).toLowerCase().replace(/[^a-z0-9]+/g, "");
  if (!role) return "";
  if (
    /evaluator|verifier|reviewer|review|testrunner|tester|quality|auditor|judge/.test(
      role,
    ) ||
    role === "qa"
  )
    return "Evaluator";
  if (
    /implementationworker|implementation|builder|implementer|developer|coder|artifactcurator|synthesizer/.test(
      role,
    )
  )
    return "Builder";
  if (/planner|architect|router|plancompiler|strategist|designer/.test(role))
    return "Planner";
  if (
    role === "pm" ||
    /productmanager|requirementanalyst|requirements|intake|scope/.test(role)
  )
    return "PM";
  return "";
}


// Infer which agent a DAG node belongs to (node-based steps have no event actor),
// so node logs attach the right artifacts (build->Builder, review->Evaluator, ...).
export function nodeActor(node: { [key: string]: unknown }): string {
  // The certified DAG already names the logical operator. Prefer that durable
  // contract (and explicit routing roles) over guesses from opaque IDs such as
  // S1/S2/S3 or broad capabilities such as "planning".
  for (const value of [
    node.logical_operator,
    node.requested_role,
    node.target_role,
    node.preferred_role,
    node.preferred_operator,
    node.selected_role,
    node.role,
  ]) {
    const actor = explicitActor(value);
    if (actor) return actor;
  }

  const caps = (
    Array.isArray(node.required_capabilities) ? node.required_capabilities : []
  )
    .map((cap) => text(cap).toLowerCase())
    .join(" ");
  const id = text(node.id || node.node_id || "node").toLowerCase();
  const combined = `${id} ${caps}`;
  if (/eval|review|verdict|gate|accept/.test(combined)) return "Evaluator";
  if (/build|impl|code|frontend|backend|server|handoff/.test(combined))
    return "Builder";
  if (/plan|design|dag|rout/.test(combined)) return "Planner";
  if (/spec|prd|intake|scope|product/.test(combined)) return "PM";
  return "Planner";
}
