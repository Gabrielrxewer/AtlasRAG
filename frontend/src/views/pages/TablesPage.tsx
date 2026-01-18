import { Box, Card, CardContent, Divider, Grid, MenuItem, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useConnections } from "../../controllers/useConnections";
import { useScans, useSchema } from "../../controllers/useScans";
import { updateColumnAnnotations, updateTableAnnotations } from "../../services/catalogService";
import TagEditor from "../components/TagEditor";

const TablesPage = () => {
  const { data: connections } = useConnections();
  const [connectionId, setConnectionId] = useState<number | undefined>();
  const { data: scans } = useScans(connectionId);
  const [scanId, setScanId] = useState<number | undefined>();
  const { data: schema } = useSchema(scanId);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Tabelas & Colunas
      </Typography>
      <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
        <TextField
          select
          label="Conexão"
          value={connectionId ?? ""}
          onChange={(event) => {
            setConnectionId(Number(event.target.value));
            setScanId(undefined);
          }}
          sx={{ minWidth: 220 }}
        >
          {connections?.map((connection) => (
            <MenuItem key={connection.id} value={connection.id}>
              {connection.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="Scan"
          value={scanId ?? ""}
          onChange={(event) => setScanId(Number(event.target.value))}
          sx={{ minWidth: 220 }}
        >
          {scans?.map((scan) => (
            <MenuItem key={scan.id} value={scan.id}>
              #{scan.id}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      <Grid container spacing={2}>
        {schema?.map((table) => (
          <Grid item xs={12} key={table.id}>
            <Card>
              <CardContent>
                <Typography variant="h6">{table.schema}.{table.name}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {table.description || "Sem descrição"}
                </Typography>
                <TagEditor
                  value={(table.annotations?.tags as string[]) || []}
                  onChange={(tags) =>
                    updateTableAnnotations(table.id, {
                      annotations: { ...(table.annotations || {}), tags }
                    })
                  }
                />
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Colunas
                </Typography>
                <Grid container spacing={2}>
                  {table.columns.map((column) => (
                    <Grid item xs={12} md={6} key={column.id}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography variant="subtitle1">{column.name}</Typography>
                          <Typography variant="body2" color="text.secondary">
                            {column.data_type}
                          </Typography>
                          <TagEditor
                            value={(column.annotations?.tags as string[]) || []}
                            onChange={(tags) =>
                              updateColumnAnnotations(column.id, {
                                annotations: { ...(column.annotations || {}), tags }
                              })
                            }
                          />
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default TablesPage;
