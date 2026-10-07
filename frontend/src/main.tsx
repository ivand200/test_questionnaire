import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";
import { AppShell } from "./components/AppShell";
import { STATUSES, type Status } from "./components/status";
import { HomePage } from "./pages/HomePage";
import { QuestionPage } from "./pages/QuestionPage";
import { SourcesPage } from "./pages/SourcesPage";

// The queue filter lives in the address as ?status=. A value that is not a status is dropped.
const rootRoute = createRootRoute({
  component: AppShell,
  validateSearch: (search: Record<string, unknown>): { status?: Status } =>
    STATUSES.includes(search.status as Status) ? { status: search.status as Status } : {},
});
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomePage,
});
const questionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/questions/$questionId",
  component: QuestionPage,
});
const sourcesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sources",
  component: SourcesPage,
});
const router = createRouter({
  routeTree: rootRoute.addChildren([indexRoute, questionRoute, sourcesRoute]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
