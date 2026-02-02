// Página de chat com agentes.
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
import { useEffect, useMemo, useState } from "react";
import { useAgentMessages, useAgents, useSendAgentMessage } from "../../application/controllers/useAgents";

const AgentChatPage = () => {
  const { data: agents = [] } = useAgents();
  const [selectedAgent, setSelectedAgent] = useState<number | "">(agents[0]?.id ?? "");
  const [message, setMessage] = useState("");
  const activeAgent = agents.find((agent) => agent.id === selectedAgent);
  const { data: messages = [] } = useAgentMessages(typeof selectedAgent === "number" ? selectedAgent : undefined);
  const sendMessage = useSendAgentMessage(typeof selectedAgent === "number" ? selectedAgent : undefined);

  useEffect(() => {
    if (agents.length && selectedAgent === "") {
      setSelectedAgent(agents[0].id);
    }
  }, [agents, selectedAgent]);

  // Lista conversas recentes para o painel lateral.
  const recentConversations = useMemo(() => {
    return agents.map((agent) => {
      const lastMessage = messages
        .filter((item) => item.agent_id === agent.id)
        .slice(-1)[0];
      return {
        id: agent.id,
        agent: agent.name,
        preview: lastMessage?.content ?? "Sem mensagens ainda",
        tag: lastMessage ? "Recente" : "Novo"
      };
    });
  }, [agents, messages]);

  const handleSend = () => {
    // Envia mensagem para o agente selecionado.
    if (!message.trim() || typeof selectedAgent !== "number") {
      return;
    }
    sendMessage.mutate(
      { content: message },
      {
        onSuccess: () => setMessage("")
      }
    );
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h3" sx={{ mb: 1 }}>
          Chat com agentes
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Escolha um agente cadastrado e inicie uma conversa. O agente usará o prompt base e as conexões
          configuradas para responder.
        </Typography>
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "280px 1fr" }, gap: 3 }}>
        <Card sx={{ height: "fit-content" }}>
          <CardContent>
            <Typography variant="subtitle1" sx={{ mb: 2 }}>
              Conversas recentes
            </Typography>
            <List disablePadding>
              {recentConversations.map((item) => (
                <ListItem key={item.id} sx={{ px: 0 }}>
                  <Box sx={{ width: "100%" }}>
                    <Stack direction="row" alignItems="center" spacing={1.5}>
                      <Avatar sx={{ width: 36, height: 36, bgcolor: "primary.main" }}>
                        {item.agent.slice(0, 1)}
                      </Avatar>
                      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                        <Typography variant="subtitle2">{item.agent}</Typography>
                        <Typography variant="body2" color="text.secondary" noWrap>
                          {item.preview}
                        </Typography>
                      </Box>
                      <Chip size="small" label={item.tag} />
                    </Stack>
                  </Box>
                </ListItem>
              ))}
              {!recentConversations.length && (
                <Typography variant="body2" color="text.secondary">
                  Nenhum agente cadastrado ainda.
                </Typography>
              )}
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
                  onChange={(event) => setSelectedAgent(event.target.value as number)}
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
                  {activeAgent?.role || "Selecione um agente para ver o perfil."}
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ mb: 2 }} />

            <Stack spacing={2} sx={{ mb: 3 }}>
              {messages.map((item) => (
                <Box key={item.id} sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
                  <Avatar sx={{ bgcolor: item.role === "user" ? "primary.main" : "secondary.main" }}>
                    {item.role === "user" ? "U" : "A"}
                  </Avatar>
                  <Box>
                    <Typography variant="subtitle2">
                      {item.role === "user" ? "Você" : activeAgent?.name}
                    </Typography>
                    <Typography variant="body2">{item.content}</Typography>
                  </Box>
                </Box>
              ))}
              {!messages.length && (
                <Typography variant="body2" color="text.secondary">
                  Nenhuma mensagem enviada ainda.
                </Typography>
              )}
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
              <Button variant="contained" onClick={handleSend} disabled={sendMessage.isPending}>
                Enviar
              </Button>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Stack>
  );
};

export default AgentChatPage;
