import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
import { isRecord } from "../api/parsing";
import type { ResultArtifact } from "./types";

/**
 * Validates and maps the backend's `ResultArtifactResponse` payload (snake_case) into the
 * client's `ResultArtifact` shape (camelCase). Returns null for anything that doesn't match, so
 * callers fall back to `invalid_response` instead of trusting arbitrary payload content.
 */
export function parseResultArtifact(payload: unknown): ResultArtifact | null {
  if (!isRecord(payload)) {
    return null;
  }

  const {
    result_artifact_id: resultArtifactId,
    scenario_session_id: scenarioSessionId,
    job_id: jobId,
    workflow_id: workflowId,
    workflow_version: workflowVersion,
    schema_ref: schemaRef,
    schema_version: schemaVersion,
    created_at: createdAt,
    output,
  } = payload;

  if (
    typeof resultArtifactId !== "string" ||
    typeof scenarioSessionId !== "string" ||
    typeof jobId !== "string" ||
    typeof workflowId !== "string" ||
    typeof workflowVersion !== "number" ||
    typeof schemaRef !== "string" ||
    typeof schemaVersion !== "number" ||
    typeof createdAt !== "string" ||
    !isRecord(output) ||
    Array.isArray(output)
  ) {
    return null;
  }

  return {
    resultArtifactId,
    scenarioSessionId,
    jobId,
    workflowId,
    workflowVersion,
    schemaRef,
    schemaVersion,
    createdAt,
    output,
  };
}

// Compile-time drift check: fails typecheck if the backend's ResultArtifactResponse schema grows,
// loses, retypes, or changes the nullability/optionality of a field parseResultArtifact() above
// doesn't know about. Also documents, at the type level, that the response has no provider/model/
// provider-call fields for parseResultArtifact() to accidentally forward.
type _ResultArtifactResponseShapeCheck = AssertExactSchemaShape<
  components["schemas"]["ResultArtifactResponse"],
  {
    created_at: string;
    job_id: string;
    output: { [key: string]: unknown };
    result_artifact_id: string;
    scenario_session_id: string;
    schema_ref: string;
    schema_version: number;
    workflow_id: string;
    workflow_version: number;
  }
>;
const _assertResultArtifactResponseShapeMatchesGenerated: _ResultArtifactResponseShapeCheck = true;
void _assertResultArtifactResponseShapeMatchesGenerated;
