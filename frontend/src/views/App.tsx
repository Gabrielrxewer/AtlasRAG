import { Box } from "@mui/material";
import { Route, Routes } from "react-router-dom";
import TopNav from "./components/TopNav";
import ConnectionsPage from "./pages/ConnectionsPage";
import ScansPage from "./pages/ScansPage";
import TablesPage from "./pages/TablesPage";
import ApiRoutesPage from "./pages/ApiRoutesPage";
import RagPlaygroundPage from "./pages/RagPlaygroundPage";

const App = () => {
  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <TopNav />
      <Box component="main" sx={{ flexGrow: 1, p: 4, bgcolor: "#f7f7fb" }}>
        <Routes>
          <Route path="/" element={<ConnectionsPage />} />
          <Route path="/scans" element={<ScansPage />} />
          <Route path="/tables" element={<TablesPage />} />
          <Route path="/api-routes" element={<ApiRoutesPage />} />
          <Route path="/rag" element={<RagPlaygroundPage />} />
        </Routes>
      </Box>
    </Box>
  );
};

export default App;
