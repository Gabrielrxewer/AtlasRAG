import { useQuery } from "@tanstack/react-query";
import { getSamples } from "../services/catalogService";

export const useSamples = (tableId?: number) => {
  return useQuery({
    queryKey: ["samples", tableId],
    queryFn: () => getSamples(tableId ?? 0),
    enabled: Boolean(tableId)
  });
};
