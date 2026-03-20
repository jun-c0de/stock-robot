import { Controller, Get } from '@nestjs/common';
import { StocksService } from './stocks.service';

@Controller('stocks') // 👈 이 부분이 'stocks'로 정확히 적혀 있나요?
export class StocksController {
  constructor(private readonly stocksService: StocksService) {}

  @Get() // 👈 Get 데코레이터가 붙어 있는지 확인하세요.
  async findAll() {
    return await this.stocksService.findAll();
  }
}
