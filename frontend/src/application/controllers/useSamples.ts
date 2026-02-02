// Hook para amostras de dados.
import { useQuery } from "@tanstack/react-query";
import { getSamples } from "../services/catalogService";

export const useSamples = (tableId?: number) => {
  // Busca amostras apenas quando há tabela selecionada.
  return useQuery({
    queryKey: ["samples", tableId],
    queryFn: () => getSamples(tableId ?? 0),
    enabled: Boolean(tableId)
  });
};
