import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import App from "../views/App";

it("renders nav", () => {
  render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
  expect(screen.getByText("AtlasRAG Console")).toBeInTheDocument();
});
