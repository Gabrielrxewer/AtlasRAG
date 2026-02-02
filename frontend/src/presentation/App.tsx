// Layout principal com navegação e rotas.
import { Box, Container, Toolbar } from "@mui/material";
import { Route, Routes } from "react-router-dom";
import TopNav from "./components/TopNav";
import ConnectionsPage from "./pages/ConnectionsPage";
import ScansPage from "./pages/ScansPage";
import TablesPage from "./pages/TablesPage";
import ApiRoutesPage from "./pages/ApiRoutesPage";
import RagPlaygroundPage from "./pages/RagPlaygroundPage";
import AgentConfigPage from "./pages/AgentConfigPage";
import AgentChatPage from "./pages/AgentChatPage";

const App = () => {
  // Estrutura a navegação e o conteúdo principal.
  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <TopNav />
      <Box component="main" sx={{ flexGrow: 1, px: { xs: 2, md: 4 }, py: 4 }}>
        <Toolbar />
        <Container maxWidth="xl" sx={{ pt: 2, pb: 6 }}>
          <Routes>
            <Route path="/" element={<ConnectionsPage />} />
            <Route path="/scans" element={<ScansPage />} />
            <Route path="/tables" element={<TablesPage />} />
            <Route path="/api-routes" element={<ApiRoutesPage />} />
            <Route path="/rag" element={<RagPlaygroundPage />} />
            <Route path="/agents" element={<AgentConfigPage />} />
            <Route path="/agent-chat" element={<AgentChatPage />} />
          </Routes>
        </Container>
      </Box>
    </Box>
  );
};

export default App;
