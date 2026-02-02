// Página de visualização de scans por conexão.
import { Box, Card, CardContent, Grid, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useConnections } from "../../application/controllers/useConnections";
import { useScans } from "../../application/controllers/useScans";

const ScansPage = () => {
  // Seleciona conexão e carrega scans.
  const { data: connections } = useConnections();
  const [connectionId, setConnectionId] = useState<number | undefined>();
  const { data: scans } = useScans(connectionId);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h3" sx={{ mb: 1 }}>
          Snapshots de Scan
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Acompanhe o status dos scans por conexão e valide o catálogo gerado.
        </Typography>
      </Box>
      <TextField
        select
        label="Conexão"
        value={connectionId ?? ""}
        onChange={(event) => setConnectionId(Number(event.target.value))}
        sx={{ maxWidth: 320 }}
      >
        {connections?.map((connection) => (
          <MenuItem key={connection.id} value={connection.id}>
            {connection.name}
          </MenuItem>
        ))}
      </TextField>

      <Grid container spacing={2}>
        {scans?.map((scan) => (
          <Grid item xs={12} md={6} key={scan.id}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography variant="h6">Scan #{scan.id}</Typography>
                <Typography variant="body2" color="text.secondary">
                  Status: {scan.status}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Iniciado: {new Date(scan.started_at).toLocaleString()}
                </Typography>
                {scan.finished_at && (
                  <Typography variant="body2" color="text.secondary">
                    Finalizado: {new Date(scan.finished_at).toLocaleString()}
                  </Typography>
                )}
                {scan.status === "failed" && scan.error_message && (
                  <Typography variant="body2" color="error" sx={{ mt: 1 }}>
                    Erro: {scan.error_message}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      {scans && scans.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          Nenhum scan encontrado para esta conexão.
        </Typography>
      )}
    </Stack>
  );
};

export default ScansPage;
