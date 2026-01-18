import { Box, Button, Card, CardContent, Grid, TextField, Typography } from "@mui/material";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useApiRoutes, useCreateApiRoute, useDeleteApiRoute } from "../../controllers/useApiRoutes";

const schema = z.object({
  name: z.string().min(2),
  base_url: z.string().url(),
  path: z.string().min(1),
  method: z.string().min(1),
  auth_type: z.string().min(1),
  description: z.string().optional()
});

type FormValues = z.infer<typeof schema>;

const ApiRoutesPage = () => {
  const { data } = useApiRoutes();
  const createMutation = useCreateApiRoute();
  const deleteMutation = useDeleteApiRoute();
  const { register, handleSubmit, reset } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { method: "POST", auth_type: "none" }
  });

  const onSubmit = (values: FormValues) => {
    createMutation.mutate(values, { onSuccess: () => reset() });
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        API Routes
      </Typography>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Nova rota
          </Typography>
          <form onSubmit={handleSubmit(onSubmit)}>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <TextField label="Nome" fullWidth {...register("name")} />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField label="Base URL" fullWidth {...register("base_url")} />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField label="Path" fullWidth {...register("path")} />
              </Grid>
              <Grid item xs={12} md={3}>
                <TextField label="Método" fullWidth {...register("method")} />
              </Grid>
              <Grid item xs={12} md={3}>
                <TextField label="Auth" fullWidth {...register("auth_type")} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField label="Descrição" fullWidth {...register("description")} />
              </Grid>
              <Grid item xs={12}>
                <Button type="submit" variant="contained">
                  Salvar
                </Button>
              </Grid>
            </Grid>
          </form>
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        {data?.map((route) => (
          <Grid item xs={12} md={6} key={route.id}>
            <Card>
              <CardContent>
                <Typography variant="h6">{route.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {route.method} {route.base_url}{route.path}
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  {route.description}
                </Typography>
                <Button
                  sx={{ mt: 2 }}
                  variant="outlined"
                  color="error"
                  onClick={() => deleteMutation.mutate(route.id)}
                >
                  Remover
                </Button>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default ApiRoutesPage;
