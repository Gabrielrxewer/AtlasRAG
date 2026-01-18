import { useMutation } from "@tanstack/react-query";
import { askRag, reindexRag } from "../services/catalogService";

export const useAskRag = () => {
  return useMutation({ mutationFn: askRag });
};

export const useReindexRag = () => {
  return useMutation({ mutationFn: reindexRag });
};
