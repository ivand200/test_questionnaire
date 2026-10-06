import { getRouteApi } from "@tanstack/react-router";

import { ReviewPanel } from "../components/ReviewPanel";
import { Workspace } from "../components/Workspace";

const route = getRouteApi("/questions/$questionId");

export function QuestionPage() {
  const { questionId } = route.useParams();
  return (
    <Workspace>
      <ReviewPanel key={questionId} questionId={questionId} />
    </Workspace>
  );
}
