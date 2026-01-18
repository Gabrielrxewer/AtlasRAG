import { Box, Chip, TextField } from "@mui/material";
import { useState } from "react";

type TagEditorProps = {
  value: string[];
  onChange: (tags: string[]) => void;
};

const TagEditor = ({ value, onChange }: TagEditorProps) => {
  const [input, setInput] = useState("");

  const addTag = (tag: string) => {
    const cleaned = tag.trim();
    if (!cleaned || value.includes(cleaned)) return;
    onChange([...value, cleaned]);
  };

  return (
    <Box>
      <TextField
        label="Tags"
        size="small"
        fullWidth
        value={input}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            addTag(input);
            setInput("");
          }
        }}
      />
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
        {value.map((tag) => (
          <Chip key={tag} label={tag} onDelete={() => onChange(value.filter((item) => item !== tag))} />
        ))}
      </Box>
    </Box>
  );
};

export default TagEditor;
