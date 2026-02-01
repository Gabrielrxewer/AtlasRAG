import {
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  List,
  ListItem,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useState } from "react";

const agents = [
  {
    id: "produto",
    name: "Especialista em Produtos",
    description: "Responde dúvidas sobre catálogo e disponibilidade."
  },
  {
    id: "suporte",
    name: "Assistente de Suporte",
    description: "Ajuda clientes a resolver incidentes e tickets."
  },
  {
    id: "financeiro",
    name: "Analista Financeiro",
    description: "Explica faturas, pagamentos e política de cobrança."
  }
];

const chatHistory = [
  {
    id: 1,
    agent: "Especialista em Produtos",
    preview: "Posso consultar o estoque em tempo real?",
    tag: "Hoje"
  },
  {
    id: 2,
    agent: "Assistente de Suporte",
    preview: "Temos SLA para incidentes críticos?",
    tag: "Ontem"
  }
];

const AgentChatPage = () => {
  const [selectedAgent, setSelectedAgent] = useState(agents[0].id);
  const [message, setMessage] = useState("");

  const activeAgent = agents.find((agent) => agent.id === selectedAgent);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Chat com agentes
      </Typography>
      <Typography variant="body1" sx={{ mb: 3 }}>
        Escolha um agente cadastrado e inicie uma conversa. O agente usará o prompt base e as conexões
        configuradas para responder.
      </Typography>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "280px 1fr" }, gap: 3 }}>
        <Card sx={{ height: "fit-content" }}>
          <CardContent>
            <Typography variant="subtitle1" sx={{ mb: 2 }}>
              Conversas recentes
            </Typography>
            <List disablePadding>
              {chatHistory.map((item) => (
                <ListItem key={item.id} sx={{ px: 0 }}>
                  <Box sx={{ width: "100%" }}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Avatar sx={{ width: 32, height: 32 }}>{item.agent.slice(0, 1)}</Avatar>
                      <Box sx={{ flexGrow: 1 }}>
                        <Typography variant="subtitle2">{item.agent}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {item.preview}
                        </Typography>
                      </Box>
                      <Chip size="small" label={item.tag} />
                    </Stack>
                  </Box>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, alignItems: "center", mb: 2 }}>
              <FormControl sx={{ minWidth: 240 }}>
                <InputLabel id="agent-select-label">Agente</InputLabel>
                <Select
                  labelId="agent-select-label"
                  label="Agente"
                  value={selectedAgent}
                  onChange={(event) => setSelectedAgent(event.target.value)}
                >
                  {agents.map((agent) => (
                    <MenuItem key={agent.id} value={agent.id}>
                      {agent.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Box>
                <Typography variant="subtitle2">Perfil do agente</Typography>
                <Typography variant="body2" color="text.secondary">
                  {activeAgent?.description}
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ mb: 2 }} />

            <Stack spacing={2} sx={{ mb: 3 }}>
              <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
                <Avatar sx={{ bgcolor: "primary.main" }}>U</Avatar>
                <Box>
                  <Typography variant="subtitle2">Você</Typography>
                  <Typography variant="body2">
                    Quais fontes externas você pode consultar para responder sobre disponibilidade?
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
                <Avatar sx={{ bgcolor: "secondary.main" }}>A</Avatar>
                <Box>
                  <Typography variant="subtitle2">{activeAgent?.name}</Typography>
                  <Typography variant="body2">
                    Posso consultar o PostgreSQL do data lake, o catálogo de produtos no MongoDB e as APIs do
                    CRM para validar disponibilidade em tempo real.
                  </Typography>
                </Box>
              </Box>
            </Stack>

            <TextField
              label="Digite sua mensagem"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              fullWidth
              multiline
              minRows={3}
              placeholder="Pergunte algo ao agente selecionado"
            />
            <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 2 }}>
              <Button variant="contained">Enviar</Button>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default AgentChatPage;
