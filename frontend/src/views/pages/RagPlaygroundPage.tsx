import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useState } from "react";
import { useAskRag, useReindexRag } from "../../controllers/useRag";
import { useConnections } from "../../controllers/useConnections";
import { useApiRoutes } from "../../controllers/useApiRoutes";

const RagPlaygroundPage = () => {
  const [question, setQuestion] = useState("");
  const { data: connections = [] } = useConnections();
  const { data: apiRoutes = [] } = useApiRoutes();
  const [selectedConnections, setSelectedConnections] = useState<number[]>([]);
  const [selectedApiRoutes, setSelectedApiRoutes] = useState<number[]>([]);
  const askMutation = useAskRag();
  const reindexMutation = useReindexRag();

  const handleAsk = () => {
    askMutation.mutate({
      question,
      scope: {
        connection_ids: selectedConnections,
        api_route_ids: selectedApiRoutes
      }
    });
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h3" sx={{ mb: 1 }}>
          RAG Playground
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Teste perguntas e acompanhe as fontes que o agente utiliza para responder.
        </Typography>
      </Box>
      <Card>
        <CardContent>
          <Typography variant="subtitle1" sx={{ mb: 2 }}>
            Fontes de dados
          </Typography>
          <Stack spacing={2}>
            <FormControl fullWidth>
              <InputLabel id="rag-connections-label">Conexões de bancos</InputLabel>
              <Select
                labelId="rag-connections-label"
                multiple
                value={selectedConnections}
                label="Conexões de bancos"
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
              <InputLabel id="rag-api-label">APIs cadastradas</InputLabel>
              <Select
                labelId="rag-api-label"
                multiple
                value={selectedApiRoutes}
                label="APIs cadastradas"
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
          </Stack>
        </CardContent>
      </Card>
      <Card sx={{ background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(14, 165, 233, 0.04))" }}>
        <CardContent>
          <Typography variant="subtitle1" sx={{ mb: 2 }}>
            Pergunta
          </Typography>
          <TextField
            fullWidth
            multiline
            minRows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, mt: 2 }}>
            <Button variant="contained" onClick={handleAsk}>
              Perguntar
            </Button>
            <Button variant="outlined" onClick={() => reindexMutation.mutate({})}>
              Reindexar catálogo
            </Button>
          </Box>
        </CardContent>
      </Card>

      {askMutation.data && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Resposta
            </Typography>
            <Typography variant="body1" sx={{ mb: 2 }}>
              {askMutation.data.answer}
            </Typography>
            <Typography variant="subtitle2">Fontes usadas</Typography>
            <Box component="ul" sx={{ pl: 2, mb: 0 }}>
              {askMutation.data.citations.map((citation, idx) => (
                <li key={`${citation.item_type}-${citation.item_id}-${idx}`}>
                  {citation.item_type} #{citation.item_id}
                </li>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
};

export default RagPlaygroundPage;
