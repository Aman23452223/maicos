export function statePillClass(state: string): string {
  switch (state) {
    case "COMPLETED":
    case "APPROVED":
      return "pill pill-ok";
    case "RUNNING":
    case "PLANNED":
      return "pill pill-muted";
    case "WAITING_APPROVAL":
    case "WAITING_INPUT":
    case "PARTIAL":
      return "pill pill-warn";
    case "FAILED":
    case "REJECTED":
      return "pill pill-bad";
    default:
      return "pill pill-muted";
  }
}
