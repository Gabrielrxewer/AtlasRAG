import { Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useAskRag, useReindexRag } from "../../controllers/useRag";

const RagPlaygroundPage = () => {
  const [question, setQuestion] = useState("");
  const askMutation = useAskRag();
  const reindexMutation = useReindexRag();

  const handleAsk = () => {
    askMutation.mutate(question);
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
