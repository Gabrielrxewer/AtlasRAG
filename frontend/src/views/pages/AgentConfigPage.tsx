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
  Switch,
  TextField,
  Typography
} from "@mui/material";
import { useMemo, useState } from "react";

const agentTemplates = [
  {
    id: "atendimento",
    name: "Atendimento ao cliente",
    description: "Focado em suporte e abertura de tickets."
  },
  {
    id: "comercial",
    name: "Especialista comercial",
    description: "Dúvidas sobre planos, preços e upsell."
  },
  {
    id: "operacoes",
    name: "Operações & logística",
    description: "Regras internas, estoque e SLA."
  }
];

const gptModels = ["GPT-4o", "GPT-4.1", "GPT-4.1-mini", "GPT-3.5 Turbo"];

const connectionOptions = [
  "PostgreSQL - Data Lake",
  "MongoDB - Catálogo de produtos",
  "API CRM",
  "API Helpdesk",
  "Redis Cache",
  "S3 Documentos"
];

const AgentConfigPage = () => {
  const [templateId, setTemplateId] = useState(agentTemplates[0].id);
  const [model, setModel] = useState(gptModels[0]);
  const [agentName, setAgentName] = useState("");
  const [agentRole, setAgentRole] = useState("");
  const [basePrompt, setBasePrompt] = useState("");
  const [ragPrompt, setRagPrompt] = useState("");
  const [connections, setConnections] = useState<string[]>([]);
  const [useDatabase, setUseDatabase] = useState(true);
  const [useApis, setUseApis] = useState(true);
  const [enableRag, setEnableRag] = useState(true);

  const summary = useMemo(
    () => ({
      connections: connections.length ? connections : ["Nenhuma fonte selecionada"],
      features: [
        enableRag ? "RAG habilitado" : "RAG desativado",
        useDatabase ? "Consulta bancos de dados" : "Sem consultas a DB",
        useApis ? "Consulta APIs" : "Sem consultas a API"
      ],
      model,
      template: agentTemplates.find((template) => template.id === templateId)?.name ?? "Não definido"
    }),
    [connections, enableRag, model, templateId, useApis, useDatabase]
  );

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Configurar Agente
      </Typography>
      <Typography variant="body1" sx={{ mb: 3 }}>
        Defina o papel do agente, o prompt base e as conexões externas que ele pode consultar para enriquecer
        as respostas.
      </Typography>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "2fr 1fr" }, gap: 3 }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Identidade do agente
              </Typography>
              <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
                <FormControl fullWidth>
                  <InputLabel id="template-label">Template do agente</InputLabel>
                  <Select
                    labelId="template-label"
                    value={templateId}
                    label="Template do agente"
                    onChange={(event) => setTemplateId(event.target.value)}
                  >
                    {agentTemplates.map((template) => (
                      <MenuItem key={template.id} value={template.id}>
                        <ListItemText primary={template.name} secondary={template.description} />
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl fullWidth>
                  <InputLabel id="model-label">Modelo GPT</InputLabel>
                  <Select
                    labelId="model-label"
                    value={model}
                    label="Modelo GPT"
                    onChange={(event) => setModel(event.target.value)}
                  >
                    {gptModels.map((option) => (
                      <MenuItem key={option} value={option}>
                        {option}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
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
              <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
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
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Fontes de dados e APIs
              </Typography>
              <FormControl fullWidth>
                <InputLabel id="connections-label">Selecione conexões e APIs</InputLabel>
                <Select
                  labelId="connections-label"
                  multiple
                  value={connections}
                  label="Selecione conexões e APIs"
                  onChange={(event) => setConnections(event.target.value as string[])}
                  renderValue={(selected) => (
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                      {(selected as string[]).map((value) => (
                        <Chip key={value} label={value} />
                      ))}
                    </Box>
                  )}
                >
                  {connectionOptions.map((option) => (
                    <MenuItem key={option} value={option}>
                      <ListItemText primary={option} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Divider sx={{ my: 3 }} />

              <FormGroup row>
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
        </Box>

        <Card sx={{ height: "fit-content" }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Resumo do agente
            </Typography>
            <Typography variant="subtitle2">Nome</Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {agentName || "Defina um nome para o agente"}
            </Typography>
            <Typography variant="subtitle2">Template</Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {summary.template}
            </Typography>
            <Typography variant="subtitle2">Modelo GPT</Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {summary.model}
            </Typography>
            <Typography variant="subtitle2">Função</Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {agentRole || "Descreva a função principal"}
            </Typography>
            <Typography variant="subtitle2">Recursos habilitados</Typography>
            <Box component="ul" sx={{ pl: 2, mb: 2 }}>
              {summary.features.map((feature) => (
                <li key={feature}>
                  <Typography variant="body2">{feature}</Typography>
                </li>
              ))}
            </Box>
            <Typography variant="subtitle2">Fontes selecionadas</Typography>
            <Box component="ul" sx={{ pl: 2, mb: 3 }}>
              {summary.connections.map((source) => (
                <li key={source}>
                  <Typography variant="body2">{source}</Typography>
                </li>
              ))}
            </Box>
            <Button variant="contained" fullWidth>
              Salvar agente
            </Button>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default AgentConfigPage;
