import { Box, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { Sample } from "../../models/types";

type SamplesViewerProps = {
  samples: Sample[];
};

const SamplesViewer = ({ samples }: SamplesViewerProps) => {
  if (samples.length === 0) {
    return <Typography variant="body2">Sem amostras disponíveis.</Typography>;
  }

  const rows = samples[0].rows;
  const columns = Object.keys(rows[0] || {});

  return (
    <Box sx={{ overflowX: "auto" }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell key={column}>{column}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, idx) => (
            <TableRow key={idx}>
              {columns.map((column) => (
                <TableCell key={column}>{String(row[column] ?? "")}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
};

export default SamplesViewer;
