import questionSchema from "../../../../../configs/kernel/schemas/generate_questions_output.schema.json";

// Use the same publication rule on historical strings when deciding what the reader can see.
const authoredText = new RegExp(questionSchema.$defs.authoredText.pattern, "u");

export function hasAuthoredText(value: string): boolean {
  return authoredText.test(value);
}
