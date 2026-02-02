import {
  AppBar,
  Avatar,
  Box,
  Divider,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Typography
} from "@mui/material";
import {
  ApiRounded,
  AutoAwesomeRounded,
  ChatRounded,
  FactCheckRounded,
  SettingsSuggestRounded,
  StorageRounded,
  TableViewRounded
} from "@mui/icons-material";
import { Link, useLocation } from "react-router-dom";

const navItems = [
  { label: "Conexões", path: "/", icon: <StorageRounded /> },
  { label: "Scans", path: "/scans", icon: <FactCheckRounded /> },
  { label: "Tabelas & Colunas", path: "/tables", icon: <TableViewRounded /> },
  { label: "API Routes", path: "/api-routes", icon: <ApiRounded /> },
  { label: "RAG Playground", path: "/rag", icon: <AutoAwesomeRounded /> },
  { label: "Configurar Agente", path: "/agents", icon: <SettingsSuggestRounded /> },
  { label: "Chat com Agentes", path: "/agent-chat", icon: <ChatRounded /> }
];

const drawerWidth = 240;

const TopNav = () => {
  const location = useLocation();

  return (
    <Box>
      <AppBar position="fixed" sx={{ zIndex: 1201 }}>
        <Toolbar>
          <Stack direction="row" alignItems="center" spacing={2}>
            <Avatar sx={{ bgcolor: "primary.main" }}>A</Avatar>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                AtlasRAG Console
              </Typography>
              <Typography variant="caption" sx={{ color: "rgba(226, 232, 240, 0.7)" }}>
                Observabilidade e inteligência para dados
              </Typography>
            </Box>
          </Stack>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: "border-box",
            mt: 9,
            px: 1.5,
            pb: 3
          }
        }}
      >
        <Box sx={{ px: 2, py: 2 }}>
          <Typography variant="caption" sx={{ textTransform: "uppercase", letterSpacing: "0.12em", color: "#94a3b8" }}>
            Navegação
          </Typography>
        </Box>
        <Divider sx={{ borderColor: "rgba(148, 163, 184, 0.2)" }} />
        <List sx={{ mt: 1 }}>
          {navItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={location.pathname === item.path}
              >
                <ListItemIcon sx={{ color: "inherit", minWidth: 36 }}>{item.icon}</ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{ fontWeight: 500, whiteSpace: "normal" }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>
    </Box>
  );
};

export default TopNav;
