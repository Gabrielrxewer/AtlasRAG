import { AppBar, Box, Drawer, List, ListItem, ListItemButton, ListItemText, Toolbar, Typography } from "@mui/material";
import { Link, useLocation } from "react-router-dom";

const navItems = [
  { label: "Conexões", path: "/" },
  { label: "Scans", path: "/scans" },
  { label: "Tabelas & Colunas", path: "/tables" },
  { label: "API Routes", path: "/api-routes" },
  { label: "RAG Playground", path: "/rag" }
];

const drawerWidth = 240;

const TopNav = () => {
  const location = useLocation();

  return (
    <Box>
      <AppBar position="fixed" sx={{ zIndex: 1201 }}>
        <Toolbar>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            AtlasRAG Console
          </Typography>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: "border-box", mt: 8 }
        }}
      >
        <List>
          {navItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={location.pathname === item.path}
              >
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>
    </Box>
  );
};

export default TopNav;
