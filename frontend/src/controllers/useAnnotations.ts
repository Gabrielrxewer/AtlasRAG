import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateColumnAnnotations, updateTableAnnotations } from "../services/catalogService";

export const useUpdateTableAnnotations = (scanId?: number) => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ tableId, payload }: { tableId: number; payload: Record<string, unknown> }) =>
      updateTableAnnotations(tableId, payload),
    onSuccess: () => {
      if (scanId) {
        client.invalidateQueries({ queryKey: ["schema", scanId] });
      }
    }
  });
};

export const useUpdateColumnAnnotations = (scanId?: number) => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ columnId, payload }: { columnId: number; payload: Record<string, unknown> }) =>
      updateColumnAnnotations(columnId, payload),
    onSuccess: () => {
      if (scanId) {
        client.invalidateQueries({ queryKey: ["schema", scanId] });
      }
    }
  });
};
