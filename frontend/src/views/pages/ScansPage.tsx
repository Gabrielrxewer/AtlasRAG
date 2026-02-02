import { Box, Card, CardContent, Grid, MenuItem, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useConnections } from "../../controllers/useConnections";
import { useScans } from "../../controllers/useScans";

const ScansPage = () => {
  const { data: connections } = useConnections();
  const [connectionId, setConnectionId] = useState<number | undefined>();
  const { data: scans } = useScans(connectionId);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Snapshots de Scan
      </Typography>
      <TextField
        select
        label="Conexão"
        value={connectionId ?? ""}
        onChange={(event) => setConnectionId(Number(event.target.value))}
        sx={{ mb: 3, minWidth: 240 }}
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
            <Card>
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
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Nenhum scan encontrado para esta conexão.
        </Typography>
      )}
    </Box>
  );
};

export default ScansPage;
