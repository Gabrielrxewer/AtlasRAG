import { Box, Button, Card, CardContent, Grid, TextField, Typography } from "@mui/material";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useConnections, useCreateConnection, useDeleteConnection, useScanConnection } from "../../controllers/useConnections";

const schema = z.object({
  name: z.string().min(2),
  host: z.string().min(2),
  port: z.coerce.number().min(1),
  database: z.string().min(1),
  username: z.string().min(1),
  password: z.string().min(1),
  ssl_mode: z.string().min(1)
});

type FormValues = z.infer<typeof schema>;

const ConnectionsPage = () => {
  const { data } = useConnections();
  const createMutation = useCreateConnection();
  const deleteMutation = useDeleteConnection();
  const scanMutation = useScanConnection();
  const { register, handleSubmit, reset, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      port: 5432,
      ssl_mode: "prefer"
    }
  });

  const onSubmit = (values: FormValues) => {
    createMutation.mutate(values, { onSuccess: () => reset() });
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Conexões externas
      </Typography>
      <Typography variant="body1" sx={{ mb: 3 }}>
        Cadastre conexões com bancos externos para que os agentes possam consultar dados fora da base principal.
        O banco padrão do aplicativo fica separado e é usado apenas para armazenar o catálogo e as conexões.
      </Typography>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Cadastrar conexão externa
          </Typography>
          <form onSubmit={handleSubmit(onSubmit)}>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <TextField label="Nome" fullWidth {...register("name")} error={!!formState.errors.name} />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField label="Host" fullWidth {...register("host")} error={!!formState.errors.host} />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField label="Port" fullWidth {...register("port")} />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField label="SSL Mode" fullWidth {...register("ssl_mode")} />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField label="Database" fullWidth {...register("database")} />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField label="User" fullWidth {...register("username")} />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField label="Password" type="password" fullWidth {...register("password")} />
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
        {data?.map((connection) => (
          <Grid item xs={12} md={6} key={connection.id}>
            <Card>
              <CardContent>
                <Typography variant="h6">{connection.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {connection.host}:{connection.port}/{connection.database}
                </Typography>
                <Box sx={{ display: "flex", gap: 1, mt: 2 }}>
                  <Button
                    variant="outlined"
                    onClick={() => scanMutation.mutate(connection.id)}
                  >
                    Scan
                  </Button>
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => deleteMutation.mutate(connection.id)}
                  >
                    Remover
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default ConnectionsPage;
