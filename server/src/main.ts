import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.enableCors();

  await app.listen(process.env.PORT ?? 3001, process.env.HOST ?? '0.0.0.0');
}

// 띄워져 있는 Promise를 catch로 잡아줍니다.
bootstrap().catch((err) => {
  console.error('Server startup error:', err);
});
