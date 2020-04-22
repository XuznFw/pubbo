# pubbo

直连 dubbo 服务进行调用

```
dubbo_client = client.DubboClient("xxx.xx.xx.xx:xxxxx")
xxx_facade = dubbo_client.proxy("com.xxx.XxxFacade")
parameter = Parameter("com.xxx.XxxRequest")
parameter.xxx = "xxx"
response = xxx_facade.xxx_method(parameter)
```

TODO
- Hessian2 协议补全
- 增加测试
