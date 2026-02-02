// Editor de pares valor/label para enums.
import { Box, Button, Grid, TextField, Typography } from "@mui/material";
import { useState } from "react";

type EnumEntry = { value: string; label: string };

type EnumMapEditorProps = {
  value: EnumEntry[];
  onChange: (entries: EnumEntry[]) => void;
};

const EnumMapEditor = ({ value, onChange }: EnumMapEditorProps) => {
  // Mantém estado local para edições rápidas.
  const [entries, setEntries] = useState<EnumEntry[]>(value);

  const updateEntry = (index: number, field: keyof EnumEntry, newValue: string) => {
    // Atualiza entrada específica e propaga mudança.
    const updated = entries.map((entry, idx) => (idx === index ? { ...entry, [field]: newValue } : entry));
    setEntries(updated);
    onChange(updated);
  };

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Enum Map
      </Typography>
      {entries.map((entry, index) => (
        <Grid container spacing={1} key={`${entry.value}-${index}`} sx={{ mb: 1 }}>
          <Grid item xs={5}>
            <TextField
              label="Value"
              size="small"
              fullWidth
              value={entry.value}
              onChange={(event) => updateEntry(index, "value", event.target.value)}
            />
          </Grid>
          <Grid item xs={5}>
            <TextField
              label="Label"
              size="small"
              fullWidth
              value={entry.label}
              onChange={(event) => updateEntry(index, "label", event.target.value)}
            />
          </Grid>
          <Grid item xs={2}>
            <Button
              variant="outlined"
              color="error"
              onClick={() => onChange(entries.filter((_, idx) => idx !== index))}
            >
              Remover
            </Button>
          </Grid>
        </Grid>
      ))}
      <Button
        variant="outlined"
        onClick={() => {
          const updated = [...entries, { value: "", label: "" }];
          setEntries(updated);
          onChange(updated);
        }}
      >
        Adicionar
      </Button>
    </Box>
  );
};

export default EnumMapEditor;
