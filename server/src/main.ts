import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.enableCors();

  await app.listen(process.env.PORT ?? 3001);
}

// 띄워져 있는 Promise를 catch로 잡아줍니다.
bootstrap().catch((err) => {
  console.error('Server startup error:', err);
});
