import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // CORS 허용 (프론트엔드에서 API 접근 가능하게 함)
  app.enableCors();

  await app.listen(process.env.PORT ?? 3001);
}
bootstrap();
