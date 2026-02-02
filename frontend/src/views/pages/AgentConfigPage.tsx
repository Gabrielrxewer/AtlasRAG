import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  FormControlLabel,
  FormGroup,
  InputLabel,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography
} from "@mui/material";
import { useMemo, useState } from "react";
import { useConnections } from "../../controllers/useConnections";
import { useApiRoutes } from "../../controllers/useApiRoutes";
import { useCreateAgent } from "../../controllers/useAgents";

const AgentConfigPage = () => {
  const { data: connections = [] } = useConnections();
  const { data: apiRoutes = [] } = useApiRoutes();
  const createAgent = useCreateAgent();
  const [template, setTemplate] = useState("");
  const [model, setModel] = useState("");
  const [agentName, setAgentName] = useState("");
  const [agentRole, setAgentRole] = useState("");
  const [basePrompt, setBasePrompt] = useState("");
  const [ragPrompt, setRagPrompt] = useState("");
  const [selectedConnections, setSelectedConnections] = useState<number[]>([]);
  const [selectedApiRoutes, setSelectedApiRoutes] = useState<number[]>([]);
  const [useDatabase, setUseDatabase] = useState(true);
  const [useApis, setUseApis] = useState(true);
  const [enableRag, setEnableRag] = useState(true);

  const summary = useMemo(
    () => ({
      connections: selectedConnections.length
        ? connections
            .filter((connection) => selectedConnections.includes(connection.id))
            .map((connection) => connection.name)
        : ["Nenhuma fonte selecionada"],
      apiRoutes: selectedApiRoutes.length
        ? apiRoutes
            .filter((route) => selectedApiRoutes.includes(route.id))
            .map((route) => route.name)
        : ["Nenhuma API selecionada"],
      features: [
        enableRag ? "RAG habilitado" : "RAG desativado",
        useDatabase ? "Consulta bancos de dados" : "Sem consultas a DB",
        useApis ? "Consulta APIs" : "Sem consultas a API"
      ],
      model: model || "Não definido",
      template: template || "Não definido"
    }),
    [
      apiRoutes,
      connections,
      enableRag,
      model,
      selectedApiRoutes,
      selectedConnections,
      template,
      useApis,
      useDatabase
    ]
  );

  const isSaveDisabled = !agentName.trim() || !model.trim() || !basePrompt.trim();

  const handleSaveAgent = () => {
    createAgent.mutate({
      name: agentName,
      role: agentRole || null,
      template: template || null,
      model: model,
      base_prompt: basePrompt,
      rag_prompt: ragPrompt || null,
      enable_rag: enableRag,
      allow_db: useDatabase,
      allow_apis: useApis,
      connection_ids: selectedConnections,
      api_route_ids: selectedApiRoutes
    });
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h3" sx={{ mb: 1 }}>
          Configurar Agente
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Defina o papel do agente, o prompt base e as conexões externas que ele pode consultar para enriquecer
          as respostas.
        </Typography>
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "2fr 1fr" }, gap: 3 }}>
        <Stack spacing={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Identidade do agente
              </Typography>
              <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
                <TextField
                  label="Template do agente"
                  value={template}
                  onChange={(event) => setTemplate(event.target.value)}
                  placeholder="Ex.: Atendimento ao cliente"
                  fullWidth
                />
                <TextField
                  label="Modelo GPT"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder="Ex.: gpt-4o-mini"
                  fullWidth
                />
                <TextField
                  label="Nome do agente"
                  value={agentName}
                  onChange={(event) => setAgentName(event.target.value)}
                  placeholder="Ex.: Especialista em produtos"
                  fullWidth
                />
                <TextField
                  label="Função principal"
                  value={agentRole}
                  onChange={(event) => setAgentRole(event.target.value)}
                  placeholder="Ex.: Responder dúvidas sobre catálogo"
                  fullWidth
                />
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Prompts
              </Typography>
              <Stack spacing={2}>
                <TextField
                  label="Prompt base do agente"
                  value={basePrompt}
                  onChange={(event) => setBasePrompt(event.target.value)}
                  multiline
                  minRows={4}
                  placeholder="Defina o contexto principal, tom de voz e responsabilidades do agente."
                  fullWidth
                />
                <TextField
                  label="Prompt de RAG (contexto adicional)"
                  value={ragPrompt}
                  onChange={(event) => setRagPrompt(event.target.value)}
                  multiline
                  minRows={4}
                  placeholder="Inclua instruções para usar conhecimento externo e histórico antes de responder."
                  fullWidth
                />
              </Stack>
            </CardContent>
          </Card>

          <Card sx={{ background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(14, 165, 233, 0.04))" }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Fontes de dados e APIs
              </Typography>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel id="connections-label">Selecione conexões de bancos</InputLabel>
                <Select
                  labelId="connections-label"
                  multiple
                  value={selectedConnections}
                  label="Selecione conexões de bancos"
                  onChange={(event) => setSelectedConnections(event.target.value as number[])}
                  renderValue={(selected) => (
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                      {(selected as number[]).map((value) => {
                        const connection = connections.find((item) => item.id === value);
                        return <Chip key={value} label={connection?.name ?? value} />;
                      })}
                    </Box>
                  )}
                >
                  {connections.map((option) => (
                    <MenuItem key={option.id} value={option.id}>
                      <ListItemText primary={option.name} secondary={`${option.host}:${option.port}`} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl fullWidth>
                <InputLabel id="api-label">Selecione APIs cadastradas</InputLabel>
                <Select
                  labelId="api-label"
                  multiple
                  value={selectedApiRoutes}
                  label="Selecione APIs cadastradas"
                  onChange={(event) => setSelectedApiRoutes(event.target.value as number[])}
                  renderValue={(selected) => (
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                      {(selected as number[]).map((value) => {
                        const route = apiRoutes.find((item) => item.id === value);
                        return <Chip key={value} label={route?.name ?? value} />;
                      })}
                    </Box>
                  )}
                >
                  {apiRoutes.map((route) => (
                    <MenuItem key={route.id} value={route.id}>
                      <ListItemText primary={route.name} secondary={`${route.method} ${route.path}`} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Divider sx={{ my: 3 }} />

              <FormGroup>
                <FormControlLabel
                  control={
                    <Switch
                      checked={useDatabase}
                      onChange={(event) => setUseDatabase(event.target.checked)}
                    />
                  }
                  label="Permitir acesso a bancos de dados"
                />
                <FormControlLabel
                  control={<Switch checked={useApis} onChange={(event) => setUseApis(event.target.checked)} />}
                  label="Permitir acesso a APIs"
                />
                <FormControlLabel
                  control={
                    <Switch checked={enableRag} onChange={(event) => setEnableRag(event.target.checked)} />
                  }
                  label="Habilitar RAG"
                />
              </FormGroup>
            </CardContent>
          </Card>
        </Stack>

        <Card sx={{ height: "fit-content", position: "sticky", top: 120 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Resumo do agente
            </Typography>
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2">Nome</Typography>
                <Typography variant="body2">
                  {agentName || "Defina um nome para o agente"}
                </Typography>
              </Box>
              <Box>
                <Typography variant="subtitle2">Template</Typography>
                <Typography variant="body2">{summary.template}</Typography>
              </Box>
              <Box>
                <Typography variant="subtitle2">Modelo GPT</Typography>
                <Typography variant="body2">{summary.model}</Typography>
              </Box>
              <Box>
                <Typography variant="subtitle2">Função</Typography>
                <Typography variant="body2">{agentRole || "Descreva a função principal"}</Typography>
              </Box>
              <Box>
                <Typography variant="subtitle2">Recursos habilitados</Typography>
                <Box component="ul" sx={{ pl: 2, mb: 0 }}>
                  {summary.features.map((feature) => (
                    <li key={feature}>
                      <Typography variant="body2">{feature}</Typography>
                    </li>
                  ))}
                </Box>
              </Box>
              <Box>
                <Typography variant="subtitle2">Conexões selecionadas</Typography>
                <Box component="ul" sx={{ pl: 2, mb: 0 }}>
                  {summary.connections.map((source) => (
                    <li key={source}>
                      <Typography variant="body2">{source}</Typography>
                    </li>
                  ))}
                </Box>
              </Box>
              <Box>
                <Typography variant="subtitle2">APIs selecionadas</Typography>
                <Box component="ul" sx={{ pl: 2, mb: 0 }}>
                  {summary.apiRoutes.map((source) => (
                    <li key={source}>
                      <Typography variant="body2">{source}</Typography>
                    </li>
                  ))}
                </Box>
              </Box>
            </Stack>
            <Button
              variant="contained"
              fullWidth
              onClick={handleSaveAgent}
              disabled={createAgent.isPending || isSaveDisabled}
              sx={{ mt: 3 }}
            >
              Salvar agente
            </Button>
          </CardContent>
        </Card>
      </Box>
    </Stack>
  );
};

export default AgentConfigPage;
