// Smoke test para renderização básica da aplicação.
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import App from "../presentation/App";

it("renders nav", () => {
  // Garante que a navegação principal aparece.
  render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
  expect(screen.getByText("AtlasRAG Console")).toBeInTheDocument();
});
