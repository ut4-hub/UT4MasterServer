using Microsoft.AspNetCore.Mvc.Formatters;
using System.Text.Json;
using UT4MasterServer.Models.Database;

namespace UT4MasterServer.Formatters;

public sealed class StatisticBaseInputFormatter : InputFormatter
{
	public StatisticBaseInputFormatter()
	{
		SupportedMediaTypes.Add("application/json");
	}

	public override async Task<InputFormatterResult> ReadRequestBodyAsync(InputFormatterContext context)
	{
		using var reader = new StreamReader(context.HttpContext.Request.Body);

		var rawValue = await reader.ReadToEndAsync();

		// the game terminates this json body with a trailing NUL character.
		// strip it only when present instead of blindly removing the last
		// character, which corrupted well-formed bodies and threw on empty ones.
		var json = rawValue.TrimEnd('\0');
		if (string.IsNullOrWhiteSpace(json))
		{
			return InputFormatterResult.Failure();
		}

		try
		{
			StatisticBase? newObject = JsonSerializer.Deserialize<StatisticBase>(json);
			if (newObject is null)
			{
				// the body was the json literal "null"
				return InputFormatterResult.Failure();
			}

			return InputFormatterResult.Success(newObject);
		}
		catch (JsonException)
		{
			return InputFormatterResult.Failure();
		}
	}

	protected override bool CanReadType(Type type)
	{
		return type == typeof(StatisticBase);
	}
}
