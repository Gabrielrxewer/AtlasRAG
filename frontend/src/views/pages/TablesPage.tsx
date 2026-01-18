import { Box, Card, CardContent, Divider, Grid, MenuItem, TextField, Typography } from "@mui/material";
import { useCallback, useRef, useState } from "react";
import { useConnections } from "../../controllers/useConnections";
import { useScans, useSchema } from "../../controllers/useScans";
import { useUpdateColumnAnnotations, useUpdateTableAnnotations } from "../../controllers/useAnnotations";
import TagEditor from "../components/TagEditor";

const TablesPage = () => {
  const { data: connections } = useConnections();
  const [connectionId, setConnectionId] = useState<number | undefined>();
  const { data: scans } = useScans(connectionId);
  const [scanId, setScanId] = useState<number | undefined>();
  const { data: schema } = useSchema(scanId);
  const updateTableMutation = useUpdateTableAnnotations(scanId);
  const updateColumnMutation = useUpdateColumnAnnotations(scanId);
  const [tableTags, setTableTags] = useState<Record<number, string[]>>({});
  const [columnTags, setColumnTags] = useState<Record<number, string[]>>({});
  const tableTimers = useRef(new Map<number, number>());
  const columnTimers = useRef(new Map<number, number>());

  const scheduleTableUpdate = useCallback(
    (tableId: number, tags: string[], baseAnnotations: Record<string, unknown> = {}) => {
      setTableTags((prev) => ({ ...prev, [tableId]: tags }));
      const existing = tableTimers.current.get(tableId);
      if (existing) window.clearTimeout(existing);
      const timeout = window.setTimeout(() => {
        updateTableMutation.mutate({
          tableId,
          payload: { annotations: { ...baseAnnotations, tags } }
        });
        tableTimers.current.delete(tableId);
      }, 400);
      tableTimers.current.set(tableId, timeout);
    },
    [updateTableMutation]
  );

  const scheduleColumnUpdate = useCallback(
    (columnId: number, tags: string[], baseAnnotations: Record<string, unknown> = {}) => {
      setColumnTags((prev) => ({ ...prev, [columnId]: tags }));
      const existing = columnTimers.current.get(columnId);
      if (existing) window.clearTimeout(existing);
      const timeout = window.setTimeout(() => {
        updateColumnMutation.mutate({
          columnId,
          payload: { annotations: { ...baseAnnotations, tags } }
        });
        columnTimers.current.delete(columnId);
      }, 400);
      columnTimers.current.set(columnId, timeout);
    },
    [updateColumnMutation]
  );

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
                  value={tableTags[table.id] || (table.annotations?.tags as string[]) || []}
                  onChange={(tags) =>
                    scheduleTableUpdate(table.id, tags, (table.annotations as Record<string, unknown>) || {})
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
                            value={columnTags[column.id] || (column.annotations?.tags as string[]) || []}
                            onChange={(tags) =>
                              scheduleColumnUpdate(
                                column.id,
                                tags,
                                (column.annotations as Record<string, unknown>) || {}
                              )
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
